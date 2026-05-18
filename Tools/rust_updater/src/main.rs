///  这个更新器一般情况下不需要再次构建，可以删除我在工作流中添加的构建流程
use std::env;
use std::fs::{self, File};
use std::io;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::thread::sleep;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::{anyhow, Context, Result};
use clap::Parser;
use log::{error, info, warn};
use simple_logger::SimpleLogger;
use zip::ZipArchive;

const MAX_WAIT_SECONDS: u64 = 60;
const MAX_COPY_RETRIES: usize = 60;

#[derive(Parser, Debug)]
#[clap(author, version, about = "Ainiee 更新器")]
struct Args {
    /// 源文件路径（ZIP文件）
    #[clap(index = 1)]
    src: String,

    /// 目标目录路径
    #[clap(index = 2)]
    dst: String,
}

/// 检查文件是否被锁定，不存在的文件视为未锁定
fn is_file_locked(filepath: &Path) -> bool {
    if !filepath.exists() {
        return false;
    }

    match File::options().read(true).write(true).open(filepath) {
        Ok(_) => false,
        Err(_) => true,
    }
}

/// 将更新包路径转换为绝对路径，避免临时更新器继承不同工作目录后找不到文件
fn resolve_update_file_path(src: &str, dst: &Path) -> PathBuf {
    let src_path = PathBuf::from(src);
    if src_path.is_absolute() {
        src_path
    } else {
        dst.join(src_path)
    }
}

/// 判断子路径是否位于父路径内
fn is_path_inside(child: &Path, parent: &Path) -> bool {
    match (child.canonicalize(), parent.canonicalize()) {
        (Ok(child), Ok(parent)) => child.starts_with(parent),
        _ => false,
    }
}

/// 如果当前 updater.exe 位于安装目录中，则复制到临时目录并重新启动，避免覆盖自身失败
fn relaunch_from_temp_if_needed(src: &Path, dst: &Path) -> Result<bool> {
    let current_exe = env::current_exe().context("无法获取当前更新器路径")?;
    if !is_path_inside(&current_exe, dst) {
        return Ok(false);
    }

    let temp_dir = env::temp_dir().join("AiNieeUpdater");
    fs::create_dir_all(&temp_dir).context("无法创建临时更新器目录")?;

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    let temp_exe = temp_dir.join(format!("updater_{}_{}.exe", std::process::id(), timestamp));

    fs::copy(&current_exe, &temp_exe).with_context(|| {
        format!(
            "无法复制更新器到临时目录: {:?} -> {:?}",
            current_exe, temp_exe
        )
    })?;

    info!("更新器位于安装目录内，切换到临时副本运行: {:?}", temp_exe);
    Command::new(&temp_exe)
        .arg(src)
        .arg(dst)
        .current_dir(dst)
        .spawn()
        .with_context(|| format!("无法启动临时更新器: {:?}", temp_exe))?;

    Ok(true)
}

/// 解压ZIP文件到指定目录
fn extract_zip(src: &Path, dst: &Path) -> Result<()> {
    let file = File::open(src).with_context(|| format!("无法打开源ZIP文件: {:?}", src))?;
    let mut archive = ZipArchive::new(file).context("无法读取ZIP文件")?;

    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let outpath = match file.enclosed_name() {
            Some(path) => dst.join(path),
            None => continue,
        };

        if file.name().ends_with('/') {
            fs::create_dir_all(&outpath)?;
        } else {
            if let Some(p) = outpath.parent() {
                if !p.exists() {
                    fs::create_dir_all(p)?;
                }
            }
            let mut outfile = File::create(&outpath)?;
            io::copy(&mut file, &mut outfile)?;
        }
    }

    Ok(())
}

/// 带重试的文件复制，自动等待 Windows 短暂释放被占用文件
fn copy_file_with_retry(src: &Path, dst: &Path) -> Result<()> {
    for attempt in 1..=MAX_COPY_RETRIES {
        match fs::copy(src, dst) {
            Ok(_) => return Ok(()),
            Err(err) if attempt < MAX_COPY_RETRIES => {
                warn!(
                    "复制文件失败，准备重试 ({}/{}): {:?} -> {:?}, 原因: {}",
                    attempt, MAX_COPY_RETRIES, src, dst, err
                );
                sleep(Duration::from_secs(1));
            }
            Err(err) => {
                return Err(anyhow!(
                    "复制文件失败: {:?} -> {:?}, 原因: {}",
                    src,
                    dst,
                    err
                ));
            }
        }
    }

    unreachable!("复制重试循环应当在成功或最终失败时返回")
}

/// 复制文件夹内容到目标目录
fn copy_directory(src: &Path, dst: &Path) -> Result<()> {
    if !src.exists() {
        return Err(anyhow!("源目录不存在: {:?}", src));
    }

    if !dst.exists() {
        fs::create_dir_all(dst)?;
    }

    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let path = entry.path();
        let target = dst.join(path.file_name().unwrap());

        if path.is_dir() {
            copy_directory(&path, &target)?;
        } else {
            copy_file_with_retry(&path, &target)?;
        }
    }

    Ok(())
}

/// 在解压目录中递归查找包含 AiNiee.exe 的目录
fn find_ainiee_dir(dir: &Path) -> Option<PathBuf> {
    // 检查当前目录是否直接包含 AiNiee.exe
    if dir.join("AiNiee.exe").exists() {
        return Some(dir.to_path_buf());
    }

    // 递归搜索子目录
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                if let Some(found) = find_ainiee_dir(&path) {
                    return Some(found);
                }
            }
        }
    }

    None
}

fn main() -> Result<()> {
    // 初始化日志
    SimpleLogger::new().init().unwrap();

    // 解析命令行参数
    let args = Args::parse();
    let dst_path = PathBuf::from(args.dst);
    let src_path = resolve_update_file_path(&args.src, &dst_path);

    info!("");

    // 先切换到临时副本运行，避免更新时覆盖正在运行的 updater.exe
    if relaunch_from_temp_if_needed(&src_path, &dst_path)? {
        info!("已启动临时更新器，当前安装目录内的更新器即将退出 …");
        return Ok(());
    }

    // 等待安装目录中的主程序退出，避免相对路径误判
    let main_exe = dst_path.join("AiNiee.exe");
    for i in 0..MAX_WAIT_SECONDS {
        if !is_file_locked(&main_exe) {
            break;
        }

        info!("准备中 {}", "…".repeat((i + 1) as usize));
        info!("Preparing {}", "…".repeat((i + 1) as usize));
        info!("");
        sleep(Duration::from_secs(1));
    }

    // 执行更新
    let result = (|| -> Result<()> {
        if is_file_locked(&main_exe) {
            return Err(anyhow!("主程序仍被占用，无法更新: {:?}", main_exe));
        }

        // 创建临时目录
        let temp_dir = dst_path.join("temp_update");
        if temp_dir.exists() {
            fs::remove_dir_all(&temp_dir)?;
        }
        fs::create_dir_all(&temp_dir)?;

        // 解压文件
        extract_zip(&src_path, &temp_dir)?;

        // 智能查找包含 AiNiee.exe 的实际内容目录
        // 支持多种zip结构: dist/AiNiee/..., AiNiee/..., 直接文件等
        let extracted_folder = find_ainiee_dir(&temp_dir)
            .ok_or_else(|| anyhow!("解压后未找到包含 AiNiee.exe 的目录"))?;

        info!("找到更新内容目录: {:?}", extracted_folder);
        copy_directory(&extracted_folder, &dst_path)?;

        fs::remove_dir_all(temp_dir)?;

        Ok(())
    })();

    if let Err(e) = fs::remove_file(&src_path) {
        error!("无法删除源文件: {:?}, 原因: {}", src_path, e);
    }

    match result {
        Ok(_) => {
            info!("文件更新成功 …");
            info!("File Update Success …");
            info!("");
        }
        Err(e) => {
            error!("文件更新失败 … {}", e);
            error!("File Update Failure … {}", e);
            info!("");
        }
    }

    info!("10 秒后自动关闭本窗口 …");
    info!("This window will automatically close in 10 seconds …");
    sleep(Duration::from_secs(10));

    Ok(())
}

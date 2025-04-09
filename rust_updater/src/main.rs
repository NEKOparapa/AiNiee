///  这个更新器一般情况下不需要再次构建，可以删除我在工作流中添加的构建流程
use std::fs::{self, File};
use std::io;
use std::path::{Path, PathBuf};
use std::thread::sleep;
use std::time::Duration;
use anyhow::{Result, Context, anyhow};
use clap::Parser;
use log::{info, error};
use simple_logger::SimpleLogger;
use zip::ZipArchive;

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

/// 检查文件是否被锁定
fn is_file_locked(filepath: &str) -> bool {
    match File::options().read(true).write(true).open(filepath) {
        Ok(_) => false,
        Err(_) => true,
    }
}

/// 解压ZIP文件到指定目录
fn extract_zip(src: &str, dst: &str) -> Result<()> {
    let file = File::open(src).context("无法打开源ZIP文件")?;
    let mut archive = ZipArchive::new(file).context("无法读取ZIP文件")?;
    
    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let outpath = match file.enclosed_name() {
            Some(path) => Path::new(dst).join(path),
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
            fs::copy(&path, &target)?;
        }
    }
    
    Ok(())
}

fn main() -> Result<()> {
    // 初始化日志
    SimpleLogger::new().init().unwrap();
    
    // 解析命令行参数
    let args = Args::parse();
    let src = args.src;
    let dst = args.dst;
    
    info!("");
    
    // 等待主程序退出
    for i in 0..60 {
        if !is_file_locked("AiNiee.exe") {
            break;
        } else {
            info!("准备中 {}", "…".repeat(i + 1));
            info!("Preparing {}", "…".repeat(i + 1));
            info!("");
            sleep(Duration::from_secs(1));
        }
    }
    
    // 执行更新
    let result = (|| -> Result<()> {
        // 创建临时目录
        let temp_dir = PathBuf::from(&dst).join("temp_update");
        if temp_dir.exists() {
            fs::remove_dir_all(&temp_dir)?;
        }
        fs::create_dir_all(&temp_dir)?;
        
        // 解压文件
        extract_zip(&src, temp_dir.to_str().unwrap())?;
        
        // 移动文件
        let extracted_folder = temp_dir.join("dist");
        copy_directory(&extracted_folder, &PathBuf::from(&dst))?;
        
       
        fs::remove_dir_all(temp_dir)?;
        
        Ok(())
    })();
    
   
    if let Err(e) = fs::remove_file(&src) {
        error!("无法删除源文件: {}", e);
    }
    

    match result {
        Ok(_) => {
            info!("文件更新成功 …");
            info!("File Update Success …");
            info!("");
        },
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

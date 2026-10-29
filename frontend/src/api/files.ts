import type { components } from './generated/schema'

export async function fileBase64(file: File) {
  if (file.size > 20 * 1024 * 1024) throw new Error('file_too_large')
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  for (let offset = 0; offset < bytes.length; offset += 8192) binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192))
  return btoa(binary)
}

export function downloadFile(file: components['schemas']['TableDownload']) {
  const bytes = Uint8Array.from(atob(file.content_base64), character => character.charCodeAt(0))
  const url = URL.createObjectURL(new Blob([bytes], { type: file.media_type }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = file.filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

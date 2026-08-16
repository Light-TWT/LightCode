# Generate multi-size icon.ico (16/32/48/64/128/256) from source PNG.
# Uses BMP/DIB encoding (not PNG) for maximum electron-builder compatibility.
$Source = "d:\works\pycharm-2025.1.1\Object\lightcode-local\electron\build\icon.png"
$Output = "d:\works\pycharm-2025.1.1\Object\lightcode-local\electron\build\icon.ico"
Add-Type -AssemblyName System.Drawing

$src = [System.Drawing.Image]::FromFile($Source)
$sizes = @(16, 32, 48, 64, 128, 256)
$dibs = @()
foreach ($s in $sizes) {
  $bmp = New-Object System.Drawing.Bitmap($s, $s, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $g.Clear([System.Drawing.Color]::Transparent)
  $g.DrawImage($src, 0, 0, $s, $s)
  $g.Dispose()

  $rect = New-Object System.Drawing.Rectangle(0, 0, $s, $s)
  $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $stride = $data.Stride
  $bytes = New-Object byte[] ($stride * $s)
  [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
  $bmp.UnlockBits($data)
  $bmp.Dispose()

  # DIB: BITMAPINFOHEADER(40) + bottom-up BGRA pixels. Top-down rows reversed.
  $pixelBytes = New-Object byte[] ($s * $s * 4)
  for ($row = 0; $row -lt $s; $row++) {
    $srcRowTop = $row                       # top-down row in LockBits
    $dstRowBottom = $s - 1 - $row           # move to bottom-up
    [Array]::Copy($bytes, $srcRowTop * $stride, $pixelBytes, $dstRowBottom * $s * 4, $s * 4)
  }

  $ms = New-Object System.IO.MemoryStream
  $w = New-Object System.IO.BinaryWriter($ms)
  $w.Write([UInt32]40)          # biSize
  $w.Write([Int32]$s)           # biWidth
  $w.Write([Int32]($s * 2))     # biHeight (XOR + AND)
  $w.Write([UInt16]1)           # biPlanes
  $w.Write([UInt16]32)          # biBitCount
  $w.Write([UInt32]0)           # biCompression
  $w.Write([UInt32]($s * $s * 4)) # biSizeImage
  $w.Write([Int32]0); $w.Write([Int32]0)  # x/y pixels per meter
  $w.Write([UInt32]0); $w.Write([UInt32]0) # clr used/important
  $w.Write($pixelBytes)
  $w.Close()
  $dibs += , $ms.ToArray()
  $ms.Dispose()
}
$src.Dispose()

$count = $sizes.Count
$fs = New-Object System.IO.BinaryWriter([System.IO.File]::Create($Output))
$fs.Write([UInt16]0)
$fs.Write([UInt16]1)
$fs.Write([UInt16]$count)
$offset = 6 + 16 * $count
for ($i = 0; $i -lt $count; $i++) {
  $s = $sizes[$i]
  $data = $dibs[$i]
  $dim = if ($s -ge 256) { 0 } else { $s }
  $fs.Write([Byte]$dim)
  $fs.Write([Byte]$dim)
  $fs.Write([Byte]0)
  $fs.Write([Byte]0)
  $fs.Write([UInt16]1)
  $fs.Write([UInt16]32)
  $fs.Write([UInt32]$data.Length)
  $fs.Write([UInt32]$offset)
  $offset += $data.Length
}
foreach ($d in $dibs) { $fs.Write($d) }
$fs.Close()
Write-Output ("icon.ico = " + (Get-Item $Output).Length + " bytes, sizes=" + ($sizes -join ','))
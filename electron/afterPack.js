// electron-builder afterPack hook: inject the app icon into the packaged EXE.
// signAndEditExecutable=false (kept to avoid winCodeSign hang) skips electron-builder's
// own icon embedding, so we do it here with rcedit after unpacking and before NSIS builds.
const { execFileSync } = require('node:child_process')
const path = require('node:path')

exports.default = async function (context) {
  const appInfo = context.packager.appInfo
  const exeName = (appInfo.executableName || appInfo.productName) + '.exe'
  const exePath = path.join(context.appOutDir, exeName)
  const icoPath = path.join(__dirname, 'build', 'icon.ico')
  const rcedit = path.join(__dirname, 'build', 'rcedit-x64.exe')
  console.log(`[afterPack] injecting icon ${icoPath} -> ${exePath}`)
  execFileSync(rcedit, [exePath, '--set-icon', icoPath], { stdio: 'inherit' })
}
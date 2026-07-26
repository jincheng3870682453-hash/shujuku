; =====================================================
; 动态数据登记系统 - 安装包脚本（v3.0 正式版）
; =====================================================

[Setup]
AppName=动态数据登记系统
AppVersion=3.0.0
AppPublisher=你的名字
DefaultDirName={autopf}\动态数据登记系统
DefaultGroupName=动态数据登记系统
OutputDir=installer
OutputBaseFilename=动态数据登记系统_Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\DynamicRegistry.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："; Flags: unchecked

[Files]
Source: "dist\DynamicRegistry.exe"; DestDir: "{app}"; Flags: ignoreversion
; ── 打包文档文件（放到安装目录） ──
Source: "更新公告.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "隐私政策.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "用户协议.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "默认账户说明.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\动态数据登记系统"; Filename: "{app}\DynamicRegistry.exe"
Name: "{autodesktop}\动态数据登记系统"; Filename: "{app}\DynamicRegistry.exe"; Tasks: desktopicon
Name: "{group}\卸载动态数据登记系统"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\DynamicRegistry.exe"; Description: "启动动态数据登记系统"; Flags: postinstall nowait skipifsilent
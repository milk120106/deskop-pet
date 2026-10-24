; Inno Setup 6 打包規範 - Desktop Pet 桌面寵物 EXE 安裝精靈
#define MyAppName "Desktop Pet 桌面寵物"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Desktop Pet Team"
#define MyAppURL "https://github.com/milk120106/deskop-pet"
#define MyAppExeName "DesktopPet.exe"
#define SourceFolder "dist\DesktopPet_Portable"

[Setup]
AppId={{91E9C7E5-6804-4B2E-B9D8-2831E0176D38}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\DesktopPet
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=auto
OutputDir=dist
OutputBaseFilename=DesktopPet_Setup_v2.1.0
SetupIconFile=assets\tray.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑 (&D)"; GroupDescription: "額外捷徑:"; Flags: checkedonce
Name: "startup"; Description: "開機自動啟動桌面寵物 (&S)"; GroupDescription: "系統整合:"; Flags: unchecked

[Files]
Source: "{#SourceFolder}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\解除安裝 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即啟動 {#MyAppName}"; Flags: nowait postinstall skipifsilent

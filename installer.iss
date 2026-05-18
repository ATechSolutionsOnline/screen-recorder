[Setup]
AppName=Screen Recorder
AppVersion=1.0.0
AppPublisher=Screen Recorder
DefaultDirName={autopf}\ScreenRecorder
DefaultGroupName=Screen Recorder
OutputDir=D:\screen-recorder\dist
OutputBaseFilename=ScreenRecorderSetup
SetupIconFile=D:\screen-recorder\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\ScreenRecorder.exe
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "D:\screen-recorder\dist\ScreenRecorder\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Screen Recorder"; Filename: "{app}\ScreenRecorder.exe"
Name: "{autodesktop}\Screen Recorder"; Filename: "{app}\ScreenRecorder.exe"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\ScreenRecorder.exe"; \
    Description: "{cm:LaunchProgram,Screen Recorder}"; \
    Flags: nowait postinstall skipifsilent

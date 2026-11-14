; Build only after compiling the matching OBS x64 DLL and freezing the companion.
; Installs only FDGCast files and leaves OBS itself untouched.
[Setup]
AppId={{C47C9B69-A4E0-4F8B-8D90-6D4CCF944210}
AppName=FDGCast
AppVersion=1.0.5-rc.1
VersionInfoVersion=1.0.5.0
AppVerName=FDGCast 1.0.5-rc.1
AppPublisher=Forged Destiny Gaming
AppPublisherURL=https://forgeddestinygaming.com/
SetupIconFile={#SourcePath}FDGCast.ico
UninstallDisplayIcon={app}\FDGCast.exe
DefaultDirName={autopf}\Forged Destiny Gaming\FDGCast
DefaultGroupName=FDGCast
OutputDir={#SourcePath}..\release
OutputBaseFilename=FDGCast-1.0.5-rc.1-win-x64-setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=FDGCast (OBS module and desktop companion)
; Requires Inno Setup 6.7 or newer for native dark styling and background colors.
WizardStyle=modern dark includetitlebar hidebevels
WizardBackColor=#151719
WizardImageFile={#SourcePath}installer\welcome.png
WizardImageBackColor=#151719
WizardSmallImageFile={#SourcePath}..\web\favicon.png
WizardSmallImageBackColor=#151719
WizardImageStretch=yes
WizardSizePercent=120
DefaultDialogFontName=Segoe UI
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
UsePreviousTasks=yes
AppSupportURL=https://hub.forgeddestinygaming.com/fdgcast
AppUpdatesURL=https://github.com/Dakotalamb/ForgeCast/releases/latest
LicenseFile={#SourcePath}..\LICENSE
; Detailed licensing remains installed alongside the full GPL texts.

[Files]
Source: "{#SourcePath}..\dist\FDGCast\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; BeforeInstall: InstallingCompanion
Source: "{#SourcePath}..\stage\forgecast\bin\64bit\forgecast.dll"; DestDir: "{commonappdata}\obs-studio\plugins\forgecast\bin\64bit"; Flags: ignoreversion; BeforeInstall: InstallingOBSModule
Source: "{#SourcePath}en-US.ini"; DestDir: "{commonappdata}\obs-studio\plugins\forgecast\data\locale"; Flags: ignoreversion
Source: "{#SourcePath}FDGCast.ico"; DestDir: "{commonappdata}\obs-studio\plugins\forgecast\data"; Flags: ignoreversion
Source: "{#SourcePath}..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\COPYING.GPL3"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\LICENSING.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\third-party-licenses\*"; DestDir: "{app}\licenses\third-party"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourcePath}..\LICENSE"; DestDir: "{commonappdata}\obs-studio\plugins\forgecast\data"; Flags: ignoreversion

Source: "{#SourcePath}..\forgecast\youtube_proto\LICENSE.txt"; DestDir: "{app}\licenses"; DestName: "YouTube-streaming-Apache-2.0.txt"; Flags: ignoreversion
Source: "{#SourcePath}..\forgecast\youtube_proto\NOTICE.txt"; DestDir: "{app}\licenses"; DestName: "YouTube-streaming-NOTICE.txt"; Flags: ignoreversion

[Registry]
Root: HKLM; Subkey: "Software\Forged Destiny Gaming\FDGCast"; ValueType: string; ValueName: "CompanionPath"; ValueData: "{app}\FDGCast.exe"; Flags: uninsdeletekey

[Icons]
Name: "{group}\FDGCast"; Filename: "{app}\FDGCast.exe"; IconFilename: "{app}\FDGCast.exe"; AppUserModelID: "ForgedDestinyGaming.FDGCast"
Name: "{autodesktop}\FDGCast"; Filename: "{app}\FDGCast.exe"; IconFilename: "{app}\FDGCast.exe"; AppUserModelID: "ForgedDestinyGaming.FDGCast"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\FDGCast.exe"; Description: "Open FDGCast Companion"; Flags: postinstall nowait skipifsilent unchecked

Filename: "https://hub.forgeddestinygaming.com/fdgcast"; Description: "Open the connection guide"; Flags: postinstall shellexec skipifsilent unchecked

[Messages]
WelcomeLabel1=Your stream starts here.
WelcomeLabel2=Version 1.0.5-rc.1 - Installer preview%n%nFDGCast brings your streaming controls, chats and vertical layouts together.%n%nThis installer includes:%n  FDGCast desktop Companion%n  FDGCast plugin for OBS Studio%n%nClose OBS and Companion before continuing.%nYour saved settings stay on this computer.
FinishedHeadingLabel=FDGCast is ready.
FinishedLabel=Next steps:%n%n1. Reopen OBS Studio.%n2. Open FDGCast Companion and go to Connections.%n3. Connect OBS and sync your platform accounts.%n%nCompanion must stay open for chat and activity.%nNothing starts streaming automatically.
BeveledLabel=FORGED DESTINY GAMING  /  1.0.5-rc.1
SelectTasksLabel2=Choose any optional shortcuts. FDGCast is always available from the Start menu.

[UninstallDelete]
; User settings and DPAPI secrets in LOCALAPPDATA are intentionally preserved on uninstall.

[InstallDelete]
; Replacing an earlier preview keeps its OBS module ID and private settings, but removes old launchers.
Type: files; Name: "{app}\ForgeCast.exe"
Type: files; Name: "{group}\ForgeCast.lnk"
Type: files; Name: "{autodesktop}\ForgeCast.lnk"



[Code]
var
  InstallPhase: String;

procedure InstallingCompanion();
begin
  InstallPhase := 'Installing FDGCast Companion...';
end;

procedure InstallingOBSModule();
begin
  InstallPhase := 'Adding the FDGCast plugin to OBS...';
end;

procedure InitializeWizard();
var
  PreviousCompanion: String;
begin
  WizardForm.WelcomeLabel1.Font.Size := 21;
  WizardForm.WelcomeLabel1.Font.Style := [fsBold];
  WizardForm.FinishedHeadingLabel.Font.Size := 21;
  WizardForm.FinishedHeadingLabel.Font.Style := [fsBold];
  if RegQueryStringValue(HKLM64, 'Software\Forged Destiny Gaming\FDGCast',
    'CompanionPath', PreviousCompanion) and FileExists(PreviousCompanion) then
  begin
    WizardForm.WelcomeLabel1.Caption := 'Ready for your next upgrade?';
    WizardForm.WelcomeLabel2.Caption :=
      'Update FDGCast to 1.0.5-rc.1.' + #13#10#13#10 +
      'Your saved connections, layouts and Windows-protected credentials stay on this computer.' + #13#10#13#10 +
      'Close OBS Studio and FDGCast Companion before continuing.' + #13#10#13#10 +
      'Setup updates Companion and the FDGCast OBS plugin together.';
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectDir then
  begin
    WizardForm.PageNameLabel.Caption := 'Choose your install location';
    WizardForm.PageDescriptionLabel.Caption := 'This folder holds Companion. The OBS plugin uses the standard shared plugin folder.';
  end;
  if CurPageID = wpReady then
  begin
    WizardForm.PageNameLabel.Caption := 'Ready to install FDGCast';
    WizardForm.PageDescriptionLabel.Caption := 'Check your choices, then install. Saved settings are preserved.';
  end;
end;

procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
begin
  if InstallPhase <> '' then WizardForm.StatusLabel.Caption := InstallPhase;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    InstallPhase := 'Finishing setup...';
    WizardForm.StatusLabel.Caption := InstallPhase;
  end;
end;

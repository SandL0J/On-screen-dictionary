; Ekran Sözlüğü (ScreenLingo) - Inno Setup Scripti
; Windows x64 Per-User Installer Yapılandırması
; Yönetici (Admin) yetkisi gerektirmeden %LOCALAPPDATA% altına kurulur.

#define MyAppName "Ekran Sözlüğü"
#define MyAppVersion "0.9.0"
#define MyAppPublisher "Ekran Sözlüğü Projesi"
#define MyAppURL "https://github.com/SandL0J/On-screen-dictionary"
#define MyAppExeName "EkranSozlugu.exe"

[Setup]
AppId={{9B7F16D8-92A3-48FA-A491-03A8D2518B99}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\EkranSozlugu
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=EkranSozlugu-Setup-v{#MyAppVersion}
SetupIconFile=app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Bilgisayar açıldığında Ekran Sözlüğü'nü otomatik başlat"; GroupDescription: "Başlangıç Ayarları:"

[Files]
Source: "..\dist\EkranSozlugu\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Filename: "{app}\{#MyAppExeName}"; Flags: nowait postinstall skipifsilent

[Registry]
; Kullanıcı başlangıç görevini seçtiyse kayıt defteri Run anahtarına da per-user güvenli kayıt aç
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "EkranSozlugu"; ValueData: """{app}\{#MyAppExeName}"" --startup"; Flags: uninsdeletevalue; Tasks: autostart

[Code]
// Kaldırma (Uninstall) sırasında kullanıcı verisi koruma denetimi
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  UserResponse: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    DataDir := GetEnv('EKRAN_SOZLUGU_DATA_DIR');
    if DataDir = '' then
      DataDir := ExpandConstant('{userappdata}\EkranSozlugu');
    if DirExists(DataDir) and (not UninstallSilent) then
    begin
      UserResponse := MsgBox(
        'Kişisel kelime defteriniz, öğrenme geçmişiniz ve ayarlarınız saklansın mı?' + #13#10 + #13#10 +
        'Konum: ' + DataDir + #13#10#13#10 +
        '• EVET (Önerilen): Verileriniz korunur. Yeniden yüklediğinizde kaldığınız yerden devam edersiniz.' + #13#10 +
        '• HAYIR: Tüm kelimeleriniz ve ayarlarınız kalıcı olarak silinir.',
        mbConfirmation, MB_YESNO
      );
      if UserResponse = IDNO then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;

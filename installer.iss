; Inno Setup Script para o Leitor Markdown Moderno
; Requer Inno Setup 6+: https://jrsoftware.org/isdl.php
; Configurado para modo --onedir (abertura ultrarrápida em 1-2 segundos)

#define MyAppName "Leitor Markdown Moderno"
#define MyAppVersion "1.0"
#define MyAppPublisher "Equipe de Desenvolvimento"
#define MyAppExeName "LeitorMD.exe"

[Setup]
AppId={{D374B0B9-93FE-49A1-B61E-C6344E0E87F1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\LeitorMD
DefaultGroupName=LeitorMD
DisableProgramGroupPage=yes
OutputDir=setup_output
OutputBaseFilename=LeitorMD_Setup
SetupIconFile=app.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "associate_md"; Description: "Associar arquivos .md ao Leitor Markdown (abrir como leitor padrão)"; GroupDescription: "Integração com o Windows:"; Flags: unchecked

[Files]
; Modo --onedir: empacota a pasta dist\LeitorMD\ inteira de forma transparente para o usuário
Source: "dist\LeitorMD\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "app.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "documento_exemplo.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Registry]
; Associação opcional de extensão .md sem sequestrar outros editores (VS Code, Obsidian, Typora)
Root: HKA; Subkey: "Software\Classes\.md"; ValueType: string; ValueName: ""; ValueData: "LeitorMD.Document"; Flags: uninsdeletevalue; Tasks: associate_md
Root: HKA; Subkey: "Software\Classes\LeitorMD.Document"; ValueType: string; ValueName: ""; ValueData: "Documento Markdown"; Flags: uninsdeletekey; Tasks: associate_md
Root: HKA; Subkey: "Software\Classes\LeitorMD.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: associate_md
Root: HKA; Subkey: "Software\Classes\LeitorMD.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: associate_md

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

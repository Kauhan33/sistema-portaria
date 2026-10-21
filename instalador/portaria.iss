; Instalador do Sistema de Portaria (Inno Setup 6)
; Gerado por build_instalador.py, que passa /DVersao=... e /DRaiz=...
;
; - Programa em C:\Arquivos de Programas\Portaria (protegido pelo Windows)
; - Dados (banco, backups, log) em C:\ProgramData\Portaria, com permissão
;   de escrita para os usuários do computador. O caminho vai para o
;   instalado.ini, lido por portaria/caminhos.py.
; - Desinstalar NÃO apaga os dados (o banco tem o histórico da portaria).

#ifndef Versao
  #define Versao "0.0.0"
#endif
#ifndef Raiz
  #define Raiz ".."
#endif

[Setup]
AppId={{6E3F2B1C-8A4D-4C55-9B1E-5D7A0C2F9A31}
AppName=Portaria da Universidade
AppVersion={#Versao}
AppVerName=Portaria da Universidade {#Versao}
AppPublisher=Projeto acadêmico — Teoria da Computação e Compiladores
DefaultDirName={autopf}\Portaria
DefaultGroupName=Portaria da Universidade
DisableProgramGroupPage=yes
; TesteSemAdmin: só para o teste automático do build (instala sem UAC)
#ifdef TesteSemAdmin
PrivilegesRequired=lowest
#else
PrivilegesRequired=admin
#endif
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile={#Raiz}\assets\portaria.ico
UninstallDisplayIcon={app}\Portaria.exe
UninstallDisplayName=Portaria da Universidade
OutputDir={#Raiz}\dist
OutputBaseFilename=Instalar_Portaria_{#Versao}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho_area"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"

[Dirs]
; pasta de dados compartilhada, com escrita para os usuários (o porteiro não é admin)
Name: "{commonappdata}\Portaria"; Permissions: users-modify; Flags: uninsneveruninstall

[Files]
Source: "{#Raiz}\dist\Portaria.exe"; DestDir: "{app}"; Flags: ignoreversion

[INI]
Filename: "{app}\instalado.ini"; Section: "Portaria"; Key: "dados"; String: "{commonappdata}\Portaria"

[Icons]
Name: "{group}\Portaria da Universidade"; Filename: "{app}\Portaria.exe"
Name: "{group}\Desinstalar a Portaria"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Portaria da Universidade"; Filename: "{app}\Portaria.exe"; Tasks: atalho_area

[Run]
Filename: "{app}\Portaria.exe"; Description: "Abrir a Portaria agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\instalado.ini"

[Messages]
ptbr.FinishedLabel=A Portaria foi instalada.%n%nOs dados (banco, backups e log) ficam em C:\ProgramData\Portaria e não são apagados ao desinstalar.

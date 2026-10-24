; ==========================================================================
;  Recette de l'installeur Windows de Recharges VE (Inno Setup 6).
;
;  Ne pas compiler ce fichier directement : lancer
;      py faire_installeur.py
;  qui vérifie le dossier construit, fournit le numéro de version et
;  produit distribution\Recharges-VE-Setup-vX.Y.Z.exe.
;
;  Règle d'or : l'installeur ne livre QUE le programme. Les données
;  (recharges.json, tarifs.json, backups\) vivent dans
;  %LOCALAPPDATA%\Recharges VE — voir _dossier_personnel() dans
;  recharges.py. Ni l'installation, ni la mise à jour, ni la
;  désinstallation n'y touchent.
; ==========================================================================

#ifndef AppVersion
  #error Lancer faire_installeur.py : il fournit le numéro de version.
#endif

; Dossiers du projet, calculés depuis l'emplacement de ce fichier.
#define Racine AddBackslash(SourcePath) + "..\"
#define Construit Racine + "dist\Recharges-VE"

[Setup]
; Identifiant permanent de l'application : c'est lui qui permet à une
; nouvelle version de reconnaître et de remplacer l'ancienne. NE JAMAIS LE
; CHANGER, sinon Windows verrait deux logiciels distincts.
AppId={{A6D14E73-2B9F-4C58-8E07-51F3C9B6D2A4}
AppName=Recharges VE
AppVersion={#AppVersion}
AppVerName=Recharges VE v{#AppVersion}
AppPublisher=andre12230-png
AppCopyright=Licence MIT

; Installation pour l'utilisateur seul, sans mot de passe administrateur :
; dans %LOCALAPPDATA%\Programs\Recharges VE, comme Pécule. Là, aucune
; donnée n'entoure l'exe : l'application choisit donc d'elle-même son
; dossier personnel (%LOCALAPPDATA%\Recharges VE).
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Recharges VE
DefaultGroupName=Recharges VE
DisableProgramGroupPage=yes
; Une mise à jour réutilise le dossier déjà choisi, sans reposer la question.
UsePreviousAppDir=yes
DisableDirPage=auto

; Programme 64 bits uniquement.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; L'application n'est jamais fermée de force (une saisie en cours serait
; perdue) : on demande à l'utilisateur de la fermer, voir [Code].
CloseApplications=no

OutputDir={#Racine}distribution
OutputBaseFilename=Recharges-VE-Setup-v{#AppVersion}
SetupIconFile={#Racine}icone_voiture.ico
UninstallDisplayIcon={app}\Recharges-VE.exe
UninstallDisplayName=Recharges VE
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

; Informations affichées dans les propriétés du fichier Setup.exe.
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Recharges VE
VersionInfoDescription=Installation de Recharges VE
VersionInfoCompany=andre12230-png

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[InstallDelete]
; Mise à jour : on vide d'abord le moteur du programme, pour qu'aucune
; bibliothèque d'une ancienne version ne traîne. Seulement _internal :
; rien d'autre dans le dossier n'est effacé.
Type: filesandordirs; Name: "{app}\_internal"

[Dirs]
; Le dossier des données existe dès l'installation, pour que le raccourci
; « Dossier des données » mène quelque part avant le premier lancement.
; Il n'est jamais supprimé à la désinstallation : ce sont les recharges.
Name: "{localappdata}\Recharges VE"; Flags: uninsneveruninstall

[Files]
; Le dossier construit par PyInstaller (Recharges-VE.exe + _internal\). Par
; sécurité, une donnée personnelle oubliée à sa racine n'est JAMAIS livrée
; (le « \ » en tête limite chaque motif à la racine du dossier : les .csv
; d'exemple de matplotlib, dans _internal, ne sont pas concernés).
Source: "{#Construit}\*"; DestDir: "{app}"; Excludes: "\recharges.json,\tarifs.json,\tarifs.json.avant,\backups,\*.csv"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Racine}LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Recharges VE"; Filename: "{app}\Recharges-VE.exe"; WorkingDir: "{app}"
Name: "{group}\Dossier des données"; Filename: "{localappdata}\Recharges VE"
Name: "{autodesktop}\Recharges VE"; Filename: "{app}\Recharges-VE.exe"; WorkingDir: "{app}"; Tasks: bureau

[Run]
Filename: "{app}\Recharges-VE.exe"; Description: "Lancer Recharges VE"; Flags: nowait postinstall skipifsilent

[Code]
{ Application ouverte pendant une mise à jour ou une désinstallation : ses
  fichiers sont occupés et le remplacement échouerait à moitié. On ne la
  ferme pas de force : on demande à l'utilisateur de le faire, et on
  s'arrête proprement s'il renonce. }

function ApplicationOuverte(): Boolean;
var
  Wmi, Resultats: Variant;
begin
  Result := False;
  try
    Wmi := CreateOleObject('WbemScripting.SWbemLocator');
    Resultats := Wmi.ConnectServer('.', 'root\CIMV2').ExecQuery(
      'SELECT ProcessId FROM Win32_Process WHERE Name = ''Recharges-VE.exe''');
    Result := Resultats.Count > 0;
  except
    { Si Windows ne sait pas répondre, on continue : au pire, Inno Setup
      signalera lui-même un fichier occupé. }
  end;
end;

function AttendreFermeture(): Boolean;
begin
  Result := True;
  while ApplicationOuverte() do
    { En mode silencieux, la réponse par défaut est « Annuler » : pas de
      boucle sans fin. }
    if SuppressibleMsgBox('Recharges VE est ouvert.' + #13#10 + #13#10 +
        'Fermez-le, puis cliquez sur OK.', mbError, MB_OKCANCEL, IDCANCEL) = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;
end;

function InitializeSetup(): Boolean;
begin
  Result := AttendreFermeture();
end;

function InitializeUninstall(): Boolean;
begin
  Result := AttendreFermeture();
end;

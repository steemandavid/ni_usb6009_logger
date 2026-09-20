; Inno Setup script for NI USB-6009 Logger.
; Build:  iscc /DAppVersion=x.y.z /DSourceDir=dist\NI6009Logger packaging\installer.iss
;
; The NI-DAQmx runtime redistributable is an OPTIONAL component. Place the
; NI downloader/offline installer as packaging\nidaqmx\nidaqmx_setup.exe
; (or point /DNiDaqSetup=<path> at it) to have the installer deploy the
; driver silently. If the file is absent, the component is skipped and the
; app's built-in driver detection guides the user instead.
;
; NOTE (Phase 6, verify on a clean Windows VM): NI's silent-install flags
; below follow NI Package Manager conventions (quiet, accept licenses,
; suppress restart). Confirm against the exact redistributable you ship.

#ifndef AppVersion
#define AppVersion "0.0.0"
#endif
#ifndef SourceDir
#define SourceDir "dist\NI6009Logger"
#endif
#ifndef NiDaqSetup
#define NiDaqSetup "nidaqmx\nidaqmx_setup.exe"
#endif

[Setup]
AppId={{8C1B6D9E-52F3-4E7A-9C64-1A2B3C4D5E6F}
AppName=NI USB-6009 Logger
AppVersion={#AppVersion}
AppPublisher=David Steeman
AppPublisherURL=https://steeman.be
DefaultDirName={autopf}\NI USB-6009 Logger
DefaultGroupName=NI USB-6009 Logger
UninstallDisplayIcon={app}\NI6009Logger.exe
OutputBaseFilename=NI6009Logger_Setup_{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
LicenseFile=..\LICENSE
WizardStyle=modern

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "{#NiDaqSetup}"; DestDir: "{tmp}\nidaqmx"; Components: nidaqmx; Check: NiDaqFileExists

[Components]
Name: "app"; Description: "NI USB-6009 Logger application"; Types: full compact custom; Flags: fixed
Name: "nidaqmx"; Description: "NI-DAQmx driver runtime (required to talk to the USB-6009; several hundred MB)"; Types: full; Check: NiDaqFileExists

[Icons]
Name: "{group}\NI USB-6009 Logger"; Filename: "{app}\NI6009Logger.exe"
Name: "{group}\Uninstall NI USB-6009 Logger"; Filename: "{uninstallexe}"
Name: "{autodesktop}\NI USB-6009 Logger"; Filename: "{app}\NI6009Logger.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "runselftest"; Description: "&Test the installation now (checks driver and DAQ)"; GroupDescription: "Verification:"; Flags: checkedonce

[Run]
; Silent NI-DAQmx install before first launch (user chose the component)
Filename: "{tmp}\nidaqmx\nidaqmx_setup.exe"; Parameters: "/q /AcceptLicenses yes /suppressrestart"; Components: nidaqmx; StatusMsg: "Installing NI-DAQmx driver (this can take several minutes)…"; Flags: runhidden waituntilterminated; Check: NiDaqFileExists

Filename: "{app}\NI6009Logger.exe"; Description: "&Launch NI USB-6009 Logger"; Flags: nowait postinstall skipifsilent

[Code]
function NiDaqFileExists(): Boolean;
begin
  Result := FileExists(ExpandConstant('{#NiDaqSetup}'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Ok: Boolean;
  Summary: String;
begin
  if CurStep = ssPostInstall and WizardIsTaskSelected('runselftest') then
  begin
    Ok := Exec(ExpandConstant('{app}\NI6009Logger.exe'), '--selftest', '', SW_HIDE,
               ewWaitUntilTerminated, ResultCode);
    if not Ok then
      Summary := 'Self-test could not run (error ' + SysErrorMessage(ResultCode) + ').'
    else if ResultCode = 0 then
      Summary := 'Driver OK and USB-6009 detected — everything works.'
    else if ResultCode = 1 then
      Summary := 'Driver OK. No DAQ device found yet.' + #13#10 +
                 'Connect the USB-6009 and launch the app; it will detect it automatically.'
    else
      Summary := 'The NI-DAQmx driver is not working yet.' + #13#10 +
                 'Reboot once (the driver may need it) and launch the app again.' + #13#10 +
                 'If it still fails, install NI-DAQmx from ni.com.';
    MsgBox('Installation test: ' + #13#10#13#10 + Summary, mbInformation, MB_OK);
  end;
end;

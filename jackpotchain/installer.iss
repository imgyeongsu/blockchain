; JackpotChain Installer Script (Inno Setup)
; 빌드: Inno Setup Compiler에서 이 파일 열고 Compile

[Setup]
AppName=JackpotChain
AppVersion=1.0.0
AppPublisher=JackpotChain Team
AppPublisherURL=https://github.com/imgyeongsu/blockchain
DefaultDirName={autopf}\JackpotChain
DefaultGroupName=JackpotChain
OutputDir=installer_output
OutputBaseFilename=JackpotChain-Setup-1.0.0
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ChangesEnvironment=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\jackpotchain.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 시작 메뉴
Name: "{group}\JackpotChain"; Filename: "{cmd}"; Parameters: "/k jackpotchain --help"; WorkingDir: "{app}"
Name: "{group}\Uninstall JackpotChain"; Filename: "{uninstallexe}"

[Registry]
; PATH 환경변수에 설치 경로 추가
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
    ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; \
    Check: NeedsAddPath(ExpandConstant('{app}'))

[Code]
// PATH에 이미 있는지 확인
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path', OrigPath)
  then begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;

// 언인스톨 시 PATH에서 제거
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Path: string;
  AppPath: string;
  P: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if RegQueryStringValue(HKEY_LOCAL_MACHINE,
      'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'Path', Path) then
    begin
      AppPath := ExpandConstant('{app}');
      P := Pos(';' + AppPath, Path);
      if P > 0 then
      begin
        Delete(Path, P, Length(';' + AppPath));
        RegWriteStringValue(HKEY_LOCAL_MACHINE,
          'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
          'Path', Path);
      end;
    end;
  end;
end;

[Run]
; 설치 후 안내 메시지
Filename: "{cmd}"; Parameters: "/c echo JackpotChain 설치 완료! 새 터미널에서 'jackpotchain --help' 실행하세요. & pause"; \
    Description: "설치 완료 메시지 보기"; Flags: postinstall shellexec

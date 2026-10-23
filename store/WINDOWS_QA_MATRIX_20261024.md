# Windows QA matrix — Web Evidence Archiver

Date: 2026-10-24

## Target policy

- Primary release QA: **Windows 11 x64**
- Secondary compatibility QA: **Windows 10 x64**, when a test machine is available
- Manifest minimum OS currently used by the Store packaging route: `10.0.19041.0`
- Expected executable: `WebEvidenceArchiver.exe`
- GitHub-hosted `windows-latest`/Windows Server build validation is useful for build/test/package automation but is **not** a substitute for Windows 11 desktop UI QA.

## Required Windows 11 checks

1. Launch the exact EXE produced from the recorded source commit.
2. 1024×768 at 100% DPI: title, primary input, primary action, status/progress, result and safety notice remain reachable.
3. Normal desktop resolution at 125% DPI.
4. Normal desktop resolution at 150% DPI.
5. Complete the core operation using non-personal test data.
6. Confirm error handling for missing/invalid input without a crash.
7. Confirm output is created only in the selected destination and source data is not unexpectedly overwritten.
8. Restart the application and repeat one normal operation.
9. Record OS build, display resolution, DPI, source commit and EXE SHA-256.
10. Capture Store screenshots only from the real application with non-personal data.

## Windows 10 secondary checks

When Windows 10 x64 is available, repeat:
- launch;
- one successful core operation;
- one expected validation/error case;
- output verification;
- 1024×768/100% DPI visibility check.

A manifest MinVersion is only a compatibility declaration. It is not evidence that Windows 10 QA passed.

## MSIX candidate checks

After an unsigned candidate exists:
- package filename/path;
- size;
- SHA-256;
- unpack succeeds;
- Identity Name / Publisher / PublisherDisplayName / DisplayName / Version / x64 match the approved inputs;
- expected EXE exists;
- embedded `SOURCE_GIT_COMMIT.txt` equals the build source HEAD.

Do not report PASS for any check that was not actually executed.

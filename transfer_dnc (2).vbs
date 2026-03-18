' transfer_dnc.vbs - Trasferisce file dal DNC TMP alla NCU via DncOCX
' Posizione: F:\ADD_ON\DNC\transfer_dnc.vbs
' Uso: cscript //Nologo "F:\ADD_ON\DNC\transfer_dnc.vbs"
' Richiede: DNCMachine.exe aperto

On Error Resume Next

Dim dnc
Set dnc = CreateObject("DncOCX.CopyDNC")

If Err.Number <> 0 Then
    WScript.Echo "ERRORE: DncOCX.CopyDNC non disponibile: " & Err.Description
    WScript.Quit(1)
End If

Err.Clear
dnc.TransferAutom

If Err.Number = 0 Then
    WScript.Echo "OK"
    WScript.Quit(0)
Else
    WScript.Echo "ERRORE: " & Err.Number & " - " & Err.Description
    WScript.Quit(2)
End If

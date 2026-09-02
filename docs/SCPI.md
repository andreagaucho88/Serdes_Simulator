# SCPI remote control (PyVISA over TCP)

Lab PRO exposes the bench as an instrument on a raw TCP socket, the same
way a DCA, a BERT or a traffic generator does. Any VISA client works:

~~~python
import pyvisa

rm = pyvisa.ResourceManager("@py")            # pyvisa-py backend, no NI runtime needed
lab = rm.open_resource("TCPIP::127.0.0.1::5025::SOCKET")
lab.read_termination = "\n"
lab.write_termination = "\n"
lab.timeout = 120000                          # procedures block until they finish

print(lab.query("*IDN?"))                     # SerDes Optical Lab PRO,LabPro,LABPRO-1,0.2.0
lab.write('CONFigure:PROFile "IEEE 802.3bs — 400GBASE-DR4 · 100G/λ ottico 500 m"')
lab.write("SOURce:PATTern:TYPE SSPRQ; ACQuire:SINGle")
print(lab.query("MEASure:EYE:TDEQ? OPTICAL"))  # TDECQ at the optical plane, dB
print(lab.query('CALCulate:DATA:EALarm? "CURRent:ER:TOTal"'))
lab.write("TRAFfic:ENABle ON; TRAFfic:WORKload ai_training")
lab.write("TRAFfic:RFC2544:RUN 64, 512, 1024")   # blocks ~40 s
print(lab.query('TRAFfic:RFC2544:RESult? "MD"'))  # Xena2544-style Markdown report
print(lab.query("SYSTem:ERRor?"))             # 0,"No error"
~~~

The server starts with the web bench (`serdes-lab` or
`python -m labpro.server`) on `127.0.0.1:5025`; change it with
`--scpi-port N` or disable it with `--no-scpi`. It is unauthenticated and
bound to the loopback interface only.

## Grammar

IEEE 488.2 conventions: commands separated by `;`, optional leading `:`,
short or long mnemonics (`MEAS:EYE:TDEQ?` ≡ `MEASure:EYE:TDEQ?`,
case-insensitive), queries end with `?`, arguments are comma-separated
(numbers, `ON|OFF`, quoted strings). Commands are synchronous: a procedure
returns when it has finished, so `*OPC?` always answers `1`. Errors are
queued (`SYSTem:ERRor?` returns `code,"message"`); a failed query sends no
response, as on a real instrument, so set a client timeout. Structured
answers are one-line JSON. `SYSTem:HELP?` lists every command.

`ACQuire:SINGle` waits for one fresh simulation record and then restores the
previous RUN/STOP state. Long SCPI procedures use the same single-flight lock
and cancellation token as the web API, so an HTTP and a SCPI experiment
cannot silently run over each other.

## Command tree

| Group | Commands | Notes |
| --- | --- | --- |
| Common | `*IDN?` `*RST` `*CLS` `*OPC?` `*WAI` `*ESR?` `*STB?` `*TST?` `SYSTem:ERRor?` `SYSTem:ERRor:COUNt?` `SYSTem:VERSion?` `SYSTem:HELP?` `SYSTem:UPTime?` | `*RST` loads the default LinkConfig and clears statistics |
| Configuration | `CONFigure:PARameter "<field>",<value>` / `?` `CONFigure:PARameter:LIST?` `CONFigure:PROFile "<name>"` / `?` `CONFigure:PRESet "<name>"` `CONFigure:HASH?` `CONFigure:ALL?` | every `LinkConfig` field, validated exactly like the HTTP API |
| Acquisition | `ACQuire:RUN` `ACQuire:STOP` `ACQuire:STATe ON|OFF` / `?` `ACQuire:RECords?` `ACQuire:CLEar` `ACQuire:SINGle` | the live bench |
| DCA (FlexDCA-like) | `MEASure:EYE:TDEQ? [node]` `MEASure:EYE:HEIGht? [node]` `MEASure:EYE:WIDTh?` `MEASure:EYE:OMA?` `MEASure:EYE:ERATio?` `MEASure:EYE:RLM?` `MEASure:EYE:SNDR?` `MEASure:EYE:ALL?` `MEASure:JITTer:RJ?` `:DJ?` `:TJ?` `:J2?` `:J9?` `:ALL?` `MEASure:COM?` `MEASure:STANdards?` | node `OPTICAL` (P at PD) or an electrical node such as `VCTLE`; measures on the last record |
| BERT ED (MP1900A-like) | `SENSe:MEASure:STARt` `SENSe:MEASure:STOP` `SENSe:MEASure:STATe?` `SENSe:PATTern:TYPE?` `CALCulate:DATA:EALarm? "<item>"` `CALCulate:DATA:PAM4?` `SENSe:ERRor:INSert <n>[,<target>]` | items: `CURRent:ER:TOTal`, `CURRent:EC:TOTal`, `CURRent:ER:MSB`, `CURRent:ER:LSB`, `CURRent:EC:MSB`, `CURRent:EC:LSB`, `CURRent:EC:INS`, `CURRent:EC:OMI`, `CURRent:SYNC:LOSS`, `CURRent:BITS`, `CURRent:SER` |
| BERT PPG (MP1900A-like) | `SOURce:PATTern:TYPE PRBS|SSPRQ|ETH|CLOCK|HEX` `SOURce:PATTern:PRBS:LENGth <n>` `SOURce:OUTPut:DATA:ENABle ON|OFF` `SOURce:JITTer:SJ:AMPLitude <UI>` `SOURce:JITTer:SJ:FREQuency <Hz>` `SOURce:JITTer:RJ:AMPLitude <fs>` `SOURce:JITTer:BUJ:AMPLitude <UI>` `SOURce:SI:AMPLitude <%>` `SOURce:SI:FREQuency <Hz>` `SOURce:BAUDrate <Bd>` `SOURce:MODulation PAM4|NRZ` `SOURce:FEC kp4|kr4|none` | all with `?` queries |
| Traffic (Xena / VIAVI) | `TRAFfic:ENABle ON|OFF` `TRAFfic:WORKload <name>` `TRAFfic:SCHeduler <name>` `TRAFfic:FRAMe:SIZE <B>` `TRAFfic:IPG <B>` `TRAFfic:STATistics?` `TRAFfic:RFC2544:RUN [sizes…]` `TRAFfic:RFC2544:RESult? [JSON|MD|XML]` `TRAFfic:Y1564:RUN` `TRAFfic:Y1564:RESult? [JSON|MD|CSV]` | reports in the Xena2544 / SAMComplete structure |
| Procedures | `PROCedure:DR4:RUN [seed]` `PROCedure:DR4:RESult?` `PROCedure:STRessed:RUN [target_dB]` `PROCedure:STRessed:RESult?` `PROCedure:GOLDen:LIBRary:RUN [MMSE|MIN_TDECQ]` `PROCedure:GOLDen:LIBRary:RESult?` `REPort:STANdards? [JSON|MD]` `REPort:BERT? [JSON|MD|CSV]` | procedures stop the live bench while they run and restart it afterwards |

Declared boundary: the mnemonics follow the instruments the bench emulates
but do not reproduce their complete grammars; the measurements behind them
are the LabPro model with its documented proxies.

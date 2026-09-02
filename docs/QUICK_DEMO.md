# Three-minute demo: watch FEC close the link

This guided path shows the central Lab PRO idea: one physical record moves
from the transmitter to the receiver while DCA, BER, and FEC observe coherent
reference planes.

## 1. Start the bench

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
serdes-lab --port 8640
~~~

Open [http://localhost:8640](http://localhost:8640), switch the UI to **EN**,
and leave acquisition in **RUN**.

## 2. Load the FEC scenario

Choose **Link with margin — FEC at work** from the educational presets. This
enables the real KP4 RS(544,514) encoder and decoder in the datapath.

Load the **Essential** view, then add these instruments from the palette:

1. **Scope / DCA**
2. **Live BER**
3. **Live FEC**

The DCA shows the analog reference plane. Live BER accumulates decisions from
compatible records. Live FEC classifies complete codewords as clean,
corrected, uncorrectable, or miscorrected.

## 3. Observe accumulation

Wait for several records:

- total bits and confidence information increase in Live BER;
- clean and corrected codeword counters increase in Live FEC;
- changing any physical control resets incompatible accumulations;
- STOP freezes the counters without changing the configuration.

## 4. Inject a controlled error

Open **BERT**, select its checker view, and inject a small error event. Watch
the same transaction at the ED pre-FEC tap and at the post-FEC tap.

The useful question is not only “what is the BER?” but:

> Where did the errors enter, did the physical RX remain locked, and did the
> decoder correct the affected codewords?

## 5. Stress the channel

Increase electrical insertion loss gradually. Compare:

- DCA eye opening at the selected reference plane;
- CDR and pattern-lock state;
- pre-FEC BER and its confidence interval;
- corrected versus uncorrectable codewords;
- the Signal chain and Checkpoint panels.

If the CDR or pattern checker loses lock, the link becomes explicitly
<code>DOWN</code>. Lab PRO does not fabricate downstream BER or GMI.

## Next experiments

- Compare the same record at driver, channel, TIA, and CTLE planes.
- Add PJ and run JTOL-lite.
- Switch to an S2P/S4P measured channel.
- Compare back-to-back, severe-channel, and noisy-receiver presets.
- Follow the [complete panel reference](PANELS.md).

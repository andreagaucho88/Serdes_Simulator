"""Loader IBIS-AMI (sperimentale, banco di prova separato dal main path).

I modelli IBIS-AMI reali sono librerie condivise compilate dal vendor
(.dll/.so/.dylib) accompagnate da un file di parametri `.ami`. Questo modulo
implementa:

- il caricamento via ctypes dell'API standard (IBIS 5.x-7.x):
    long AMI_Init(double *impulse_matrix, long row_size, long aggressors,
                  double sample_interval, double bit_time,
                  char *AMI_parameters_in, char **AMI_parameters_out,
                  void **AMI_memory_handle, char **msg)
    long AMI_GetWave(double *wave, long wave_size, double *clock_times,
                     char **AMI_parameters_out, void *AMI_memory)
    long AMI_Close(void *AMI_memory)
- un parser minimale del formato ad albero `.ami` (S-expression);
- la generazione/compilazione opzionale di un modello demo in C per testare
  il meccanismo senza binari vendor.

Nota di onestà: eseguire un binario AMI significa eseguire codice del vendor;
il risultato è "reale" quanto il modello. Questo banco non applica il modello
al percorso principale: mostra impulse/waveform prima e dopo.
"""

from __future__ import annotations

import ctypes
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Parser minimale del formato .ami (albero di S-expression)
# ---------------------------------------------------------------------------

def parse_ami_tree(text: str):
    """Parsa un file .ami in una struttura annidata [nome, figli...]."""
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "|":  # commento fino a fine riga
            while i < n and text[i] != "\n":
                i += 1
        elif c in "()":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 1
            tokens.append(text[i + 1:j])
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()"|':
                j += 1
            tokens.append(text[i:j])
            i = j

    pos = 0

    def parse():
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError(".ami incompleto")
        tok = tokens[pos]
        if tok == "(":
            pos += 1
            node = []
            while pos < len(tokens) and tokens[pos] != ")":
                node.append(parse())
            if pos >= len(tokens):
                raise ValueError("parentesi non chiusa nel .ami")
            pos += 1  # consuma ')'
            return node
        pos += 1
        return tok

    tree = parse()
    return tree


def ami_tree_to_dict(node):
    """Converte l'albero in dict annidato per visualizzazione."""
    if not isinstance(node, list):
        return node
    if not node:
        return {}
    name = node[0] if isinstance(node[0], str) else "?"
    children = node[1:]
    if all(not isinstance(c, list) for c in children):
        return {name: children if len(children) != 1 else children[0]}
    out = {}
    for c in children:
        d = ami_tree_to_dict(c)
        if isinstance(d, dict):
            out.update(d)
        else:
            out.setdefault("_values", []).append(d)
    return {name: out}


# ---------------------------------------------------------------------------
# Loader ctypes
# ---------------------------------------------------------------------------

@dataclass
class AmiRunResult:
    ok: bool
    returned: int
    output: np.ndarray | None
    params_out: str = ""
    msg: str = ""
    error: str = ""


class AmiModel:
    """Wrapper ctypes di una libreria IBIS-AMI."""

    def __init__(self, lib_path: str):
        self.lib_path = str(lib_path)
        self.lib = ctypes.CDLL(self.lib_path)
        self._memory = ctypes.c_void_p(None)
        self._closed = True

        self._init = self.lib.AMI_Init
        self._init.restype = ctypes.c_long
        self._init.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_long,
            ctypes.c_double, ctypes.c_double, ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_char_p),
        ]
        self._getwave = getattr(self.lib, "AMI_GetWave", None)
        if self._getwave is not None:
            self._getwave.restype = ctypes.c_long
            self._getwave.argtypes = [
                ctypes.POINTER(ctypes.c_double), ctypes.c_long,
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_char_p), ctypes.c_void_p,
            ]
        self._close = getattr(self.lib, "AMI_Close", None)
        if self._close is not None:
            self._close.restype = ctypes.c_long
            self._close.argtypes = [ctypes.c_void_p]

    @property
    def has_getwave(self) -> bool:
        return self._getwave is not None

    def init(self, impulse: np.ndarray, sample_interval_s: float,
             bit_time_s: float, params_in: str = "(model)") -> AmiRunResult:
        buf = np.ascontiguousarray(np.asarray(impulse, dtype=np.float64).copy())
        params_out = ctypes.c_char_p(None)
        msg = ctypes.c_char_p(None)
        self._memory = ctypes.c_void_p(None)
        try:
            ret = self._init(
                buf.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                ctypes.c_long(len(buf)), ctypes.c_long(0),
                ctypes.c_double(sample_interval_s), ctypes.c_double(bit_time_s),
                params_in.encode(), ctypes.byref(params_out),
                ctypes.byref(self._memory), ctypes.byref(msg))
        except Exception as exc:
            return AmiRunResult(False, -1, None, error=f"AMI_Init: {exc}")
        self._closed = False
        return AmiRunResult(
            ok=bool(ret), returned=int(ret), output=buf,
            params_out=(params_out.value or b"").decode(errors="replace"),
            msg=(msg.value or b"").decode(errors="replace"))

    def getwave(self, wave: np.ndarray) -> AmiRunResult:
        if self._getwave is None:
            return AmiRunResult(False, -1, None,
                                error="il modello non esporta AMI_GetWave "
                                      "(modello Init-only / LTI)")
        buf = np.ascontiguousarray(np.asarray(wave, dtype=np.float64).copy())
        clock = np.zeros(max(len(buf) // 8, 8), dtype=np.float64)
        params_out = ctypes.c_char_p(None)
        try:
            ret = self._getwave(
                buf.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                ctypes.c_long(len(buf)),
                clock.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                ctypes.byref(params_out), self._memory)
        except Exception as exc:
            return AmiRunResult(False, -1, None, error=f"AMI_GetWave: {exc}")
        return AmiRunResult(
            ok=bool(ret), returned=int(ret), output=buf,
            params_out=(params_out.value or b"").decode(errors="replace"))

    def close(self):
        if self._close is not None and not self._closed:
            try:
                self._close(self._memory)
            finally:
                self._closed = True


# ---------------------------------------------------------------------------
# Modello demo in C (per testare il meccanismo senza binari vendor)
# ---------------------------------------------------------------------------

DEMO_AMI_C = r"""
/* Demo IBIS-AMI didattico: TX Init-only FFE 3 tap + GetWave saturante.
   Compilazione: cc -O2 -shared -o demo_tx_ami.dylib demo_tx_ami.c   */
#include <stdlib.h>
#include <string.h>

static char params_out_buf[256];
static char msg_buf[256];

long AMI_Init(double *impulse_matrix, long row_size, long aggressors,
              double sample_interval, double bit_time,
              char *AMI_parameters_in, char **AMI_parameters_out,
              void **AMI_memory_handle, char **msg)
{
    (void)aggressors; (void)AMI_parameters_in;
    /* FFE 3 tap (-0.10, 1.0, -0.20) a spaziatura di 1 bit_time */
    long ui = (long)(bit_time / sample_interval + 0.5);
    if (ui < 1) ui = 1;
    double *tmp = (double *)malloc(sizeof(double) * row_size);
    if (!tmp) return 0;
    memcpy(tmp, impulse_matrix, sizeof(double) * row_size);
    for (long i = 0; i < row_size; i++) {
        double acc = 1.0 * tmp[i];
        if (i >= ui)            acc += -0.10 * tmp[i - ui];
        if (i + ui < row_size)  acc += -0.20 * tmp[i + ui];
        impulse_matrix[i] = acc;
    }
    free(tmp);
    strcpy(params_out_buf, "(demo_tx (ffe_taps 3))");
    strcpy(msg_buf, "demo_tx_ami: Init OK (FFE -0.10/1.0/-0.20)");
    *AMI_parameters_out = params_out_buf;
    *msg = msg_buf;
    *AMI_memory_handle = (void *)params_out_buf;  /* nessuno stato reale */
    return 1;
}

long AMI_GetWave(double *wave, long wave_size, double *clock_times,
                 char **AMI_parameters_out, void *AMI_memory)
{
    (void)clock_times; (void)AMI_memory;
    /* saturazione morbida tanh-like: dimostra un comportamento NLTV-ready */
    for (long i = 0; i < wave_size; i++) {
        double x = wave[i] * 1.2;
        double x2 = x * x;
        wave[i] = x * (27.0 + x2) / (27.0 + 9.0 * x2);  /* pade' tanh */
    }
    *AMI_parameters_out = params_out_buf;
    return 1;
}

long AMI_Close(void *AMI_memory)
{
    (void)AMI_memory;
    return 1;
}
"""


def build_demo_model(target_dir: str) -> str:
    """Compila il modello demo; ritorna il path della libreria o solleva."""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    src = target / "demo_tx_ami.c"
    lib = target / "demo_tx_ami.dylib"
    src.write_text(DEMO_AMI_C)
    result = subprocess.run(
        ["cc", "-O2", "-shared", "-o", str(lib), str(src)],
        capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"compilazione fallita: {result.stderr[:400]}")
    return str(lib)

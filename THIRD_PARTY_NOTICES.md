# Third-party notices

The MIT License in [LICENSE](LICENSE) applies to the original source code of
SerDes Optical Lab PRO. It does not replace the licenses or rights attached to
the third-party components and reference material listed below.

## Plotly.js 2.35.2

- Component: `labpro/static/plotly.min.js`
- Upstream: <https://github.com/plotly/plotly.js/tree/v2.35.2>
- License: MIT
- Copyright: Plotly, Inc.
- Included license: `labpro/static/plotly.min.js.LICENSE.txt`

The checked-in bundle is taken from the official `plotly.js-dist-min@2.35.2`
distribution so that the application remains usable without a CDN.

## IBM Plex Sans and IBM Plex Mono

- Components: `labpro/static/fonts/ibm-plex-*.woff2`
- Upstream distribution: <https://github.com/google/fonts/tree/main/ofl>
- License: SIL Open Font License 1.1
- Copyright: 2017 IBM Corp.
- Reserved Font Name: `Plex`
- Included license: `labpro/static/fonts/OFL-IBM-Plex.txt`

The repository redistributes Latin WOFF2 subsets obtained from official
Google Fonts endpoints without further modification. The font files remain
under the OFL 1.1 and are not relicensed under this project's MIT License.

## Space Grotesk

- Components: `labpro/static/fonts/space-grotesk-*.woff2`
- Upstream: <https://github.com/floriankarsten/space-grotesk>
- Distribution: <https://github.com/google/fonts/tree/main/ofl/spacegrotesk>
- License: SIL Open Font License 1.1
- Copyright: 2020 The Space Grotesk Project Authors
- Included license: `labpro/static/fonts/OFL-Space-Grotesk.txt`

The repository redistributes Latin WOFF2 subsets obtained from official
Google Fonts endpoints without further modification. The font files remain
under the OFL 1.1 and are not relicensed under this project's MIT License.

## IEEE 802.3 public reference material

`serdes_sim/blocks/ssprq_data.py` contains a packed copy of the public
machine-readable SSPRQ sequence available from:

<https://www.ieee802.org/3/publication/bs/SSPRQ_sequence.csv>

The source URL, decoded length, and SHA-256 digest are preserved in the code.
IEEE names, standards designations, and reference data remain attributable to
their respective rights holders. Their inclusion is for educational,
interoperability, and verification purposes and does not transfer those
materials under this project's MIT License. Downstream redistributors are
responsible for confirming that their intended use is permitted.

References to IEEE, OIF, commercial instruments, and product names are
descriptive. They do not imply endorsement, certification, trademark
ownership, or standards compliance.

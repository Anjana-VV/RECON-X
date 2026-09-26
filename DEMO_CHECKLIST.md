# RECON-X Demo Checklist

## Before Demo

- Start the backend: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
- Start the frontend: `python -m http.server 5500 --directory frontend`
- Verify `http://127.0.0.1:8000/health` returns `{"status":"ok","service":"RECON-X"}`.
- Verify `dataset/generated/incident_disk.img` exists.
- Open `http://127.0.0.1:5500/`.

## Demo

1. Introduce RECON-X as an evidence-confidence workstation.
2. Open Evidence and upload `dataset/generated/incident_disk.img`.
3. Show the calculated SHA-256.
4. Start analysis.
5. Show six detected JPEG candidates.
6. Show five recovered artifacts and one uncertain artifact.
7. Open a recovered artifact and show its preview.
8. Show the measured confidence dimensions and any `Not established` values.
9. Show the OBSERVED, RECONSTRUCTED, INFERRED, and UNKNOWN evidence states.
10. Open the Analysis pipeline.
11. Open Case Information and review the source metadata.
12. Open the unreliable artifact and show that its preview is unavailable.
13. Explain that RECON-X does not fabricate missing evidence or infer unavailable measurements.

## After Demo

- Stop the backend and frontend services if required.

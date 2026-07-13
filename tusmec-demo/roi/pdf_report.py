"""ROI PDF raporu — bonus görev (+15 puan).

ReportLab ile A4 rapor üretir: Tusmec lacivert başlık bandı, girdi/çıktı
tabloları, istemciden gelen Chart.js grafiğinin PNG görüntüsü ve
kalibrasyon dipnotu. Türkçe karakterler için DejaVu Sans gömülür.
"""
from __future__ import annotations

import base64
import io
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

NAVY = colors.HexColor("#16263f")
NAVY2 = colors.HexColor("#1e3355")
TEAL = colors.HexColor("#2bbfc4")
INK_DIM = colors.HexColor("#5a6b84")

_FONT_DIRS = [Path("/usr/share/fonts/truetype/dejavu")]
_registered = False


def _register_fonts() -> tuple[str, str]:
    """DejaVu'yu kaydet (Türkçe glifler); bulunamazsa Helvetica'ya düş."""
    global _registered
    for d in _FONT_DIRS:
        reg, bold = d / "DejaVuSans.ttf", d / "DejaVuSans-Bold.ttf"
        if reg.exists() and bold.exists():
            if not _registered:
                pdfmetrics.registerFont(TTFont("DVS", str(reg)))
                pdfmetrics.registerFont(TTFont("DVS-B", str(bold)))
                _registered = True
            return "DVS", "DVS-B"
    return "Helvetica", "Helvetica-Bold"


def _tl(v: float) -> str:
    return f"{v:,.0f} TL".replace(",", ".")


def _row(c, y, label, value, font, bold, x=20 * mm, w=170 * mm):
    c.setFont(font, 9.5)
    c.setFillColor(INK_DIM)
    c.drawString(x, y, label)
    c.setFont(bold, 9.5)
    c.setFillColor(colors.black)
    c.drawRightString(x + w, y, value)
    c.setStrokeColor(colors.HexColor("#e3e8f0"))
    c.setLineWidth(0.4)
    c.line(x, y - 2.2 * mm, x + w, y - 2.2 * mm)
    return y - 7.5 * mm


def build_roi_pdf(payload: dict) -> bytes:
    """payload: {task_label, inputs{...}, outputs{...}, chart_png(dataURL, ops.)}"""
    font, bold = _register_fonts()
    inp, out = payload["inputs"], payload["outputs"]
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    W, H = A4

    # --- başlık bandı ---
    c.setFillColor(NAVY)
    c.rect(0, H - 30 * mm, W, 30 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(bold, 16)
    c.drawString(20 * mm, H - 16 * mm, "TUSMEC")
    c.setFillColor(TEAL)
    c.setFont(font, 9)
    c.drawString(20 * mm, H - 22 * mm, "Heterojen Sürü Robotik — ROI Raporu")
    c.setFillColor(colors.white)
    c.setFont(font, 9)
    c.drawRightString(W - 20 * mm, H - 16 * mm, date.today().strftime("%d.%m.%Y"))
    c.drawRightString(W - 20 * mm, H - 22 * mm, payload.get("task_label", ""))

    y = H - 42 * mm

    # --- girdiler ---
    c.setFillColor(NAVY2); c.setFont(bold, 11)
    c.drawString(20 * mm, y, "Girdiler"); y -= 8 * mm
    y = _row(c, y, "Mevcut operasyon maliyeti (işçilik + yakıt + bakım)",
             _tl(inp["current_monthly_cost"]) + " / ay", font, bold)
    y = _row(c, y, "Tusmec lisans ücreti (aylık SaaS)",
             _tl(inp["tusmec_monthly_license"]) + " / ay", font, bold)
    y = _row(c, y, "Filo işletme maliyeti" + payload.get("fleet_source", ""),
             _tl(inp["fleet_monthly_operating"]) + " / ay", font, bold)
    y = _row(c, y, "Kurulum maliyeti (bir defalık)", _tl(inp["setup_cost"]), font, bold)
    if payload.get("fleet_desc"):
        y = _row(c, y, "Hedef filo konfigürasyonu", payload["fleet_desc"], font, bold)
    if payload.get("area_m2"):
        y = _row(c, y, "Alan büyüklüğü", f"{payload['area_m2']:,.0f} m²".replace(",", "."), font, bold)
    y = _row(c, y, "USD kuru", f"{inp['usd_rate']:.2f} TL", font, bold)

    y -= 4 * mm

    # --- çıktılar ---
    c.setFillColor(NAVY2); c.setFont(bold, 11)
    c.drawString(20 * mm, y, "Sonuçlar"); y -= 8 * mm
    payback = out["payback_months"]
    payback_txt = ("tasarruf yok" if payback is None
                   else "ilk aydan itibaren" if payback == 0
                   else f"{payback} ay")
    y = _row(c, y, "Aylık tasarruf",
             f"{_tl(out['monthly_saving_tl'])}  (${out['monthly_saving_usd']:,.0f})", font, bold)
    y = _row(c, y, "Yıllık tasarruf",
             f"{_tl(out['annual_saving_tl'])}  (${out['annual_saving_usd']:,.0f})", font, bold)
    y = _row(c, y, "Geri ödeme süresi", payback_txt, font, bold)
    y = _row(c, y, "5 yıllık toplam ROI", f"%{out['five_year_roi_pct']}", font, bold)

    # --- grafik ---
    chart = payload.get("chart_png", "")
    if chart.startswith("data:image/png;base64,"):
        try:
            img = ImageReader(io.BytesIO(base64.b64decode(chart.split(",", 1)[1])))
            iw, ih = img.getSize()
            w = 170 * mm
            h = w * ih / iw
            y -= h + 6 * mm
            c.setFillColor(NAVY2); c.setFont(bold, 11)
            c.drawString(20 * mm, y + h + 2 * mm, "Tusmec çözümü ile mevcut durum karşılaştırması")
            c.drawImage(img, 20 * mm, y, width=w, height=h,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass  # bozuk görüntü PDF'i engellemesin

    # --- dipnot ---
    c.setFont(font, 7.5)
    c.setFillColor(INK_DIM)
    c.drawString(20 * mm, 14 * mm,
                 "Bu rapor Tusmec sürü simülasyon platformu tarafından üretilmiştir. "
                 "Simülasyondan türetilen maliyetler spec kalibrasyonuna tabidir.")
    c.setFillColor(TEAL)
    c.rect(0, 0, W, 6 * mm, stroke=0, fill=1)

    c.showPage()
    c.save()
    return buf.getvalue()

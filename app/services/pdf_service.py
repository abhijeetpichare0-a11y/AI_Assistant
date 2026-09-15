import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from sqlalchemy.orm import Session
from app.models import Appointment, Customer, Business, Service, Staff

STATIC_PDF_DIR = os.path.join(os.getcwd(), "static", "pdfs")
os.makedirs(STATIC_PDF_DIR, exist_ok=True)


def generate_appointment_pdf(db: Session, appointment: Appointment, base_url: str = "http://127.0.0.1:8000") -> str:
    """
    Generate an attractive, professional appointment confirmation PDF pass.
    Returns the file path and local HTTP URL to access/download the PDF.
    """
    # Fetch related records
    customer = db.get(Customer, appointment.customer_id) if appointment.customer_id else None
    business = db.get(Business, appointment.business_id) if appointment.business_id else None
    service = db.get(Service, appointment.service_id) if appointment.service_id else None
    staff = db.get(Staff, appointment.staff_id) if appointment.staff_id else None

    biz_name = business.name if business else "GlowCare Salon & Spa"
    biz_phone = business.phone if business else "+91-9000000000"
    biz_email = getattr(business, "email", None) or "hello@glowcare.example"
    biz_location = business.location if business else "FC Road, Pune, Maharashtra, India"
    currency = business.currency if (business and business.currency) else "INR"

    cust_name = customer.name if customer else "Valued Customer"
    cust_phone = customer.phone if customer else "N/A"
    cust_email = customer.email if (customer and customer.email) else "N/A"

    service_name = service.name if service else (appointment.event_type or "Specialized Service")
    duration = service.duration_minutes if service else 30
    price = float(service.price) if (service and service.price) else 400.0
    deposit_pct = float(service.deposit_percentage or 0) if service else 0.0

    staff_name = staff.name if staff else "Any Available Specialist"
    if staff and staff.role:
        staff_name += f" ({staff.role})"

    pass_id = f"GC-PASS-{appointment.id:05d}"
    filename = f"appointment_pass_{appointment.id}.pdf"
    filepath = os.path.join(STATIC_PDF_DIR, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#0F172A'),
        alignment=TA_LEFT
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569'),
        alignment=TA_LEFT
    )

    header_right_style = ParagraphStyle(
        'HeaderRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        alignment=TA_RIGHT
    )

    pass_badge_style = ParagraphStyle(
        'PassBadge',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#0284C7'),
        alignment=TA_CENTER
    )

    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0F172A')
    )

    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )

    val_style = ParagraphStyle(
        'ValStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#0F172A')
    )

    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#64748B'),
        alignment=TA_CENTER
    )

    elements = []

    # 1. HEADER BRANDING TABLE
    header_left = [
        Paragraph(f"<b>{biz_name}</b>", title_style),
        Paragraph("Premium Beauty, Hair & Wellness Salon & Spa", subtitle_style)
    ]
    header_right = [
        Paragraph(f"📍 <b>Location</b>: {biz_location}", header_right_style),
        Paragraph(f"📞 <b>Phone</b>: {biz_phone}", header_right_style),
        Paragraph(f"📧 <b>Email</b>: {biz_email}", header_right_style)
    ]

    header_table = Table(
        [[header_left, header_right]],
        colWidths=[300, 240]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceAfter=12))

    # 2. CONFIRMED PASS BANNER
    pass_data = [
        [Paragraph(f"🎉 <b>CONFIRMED APPOINTMENT PASS</b> &nbsp;|&nbsp; PASS ID: <b>{pass_id}</b>", pass_badge_style)]
    ]
    pass_table = Table(pass_data, colWidths=[540])
    pass_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0F9FF')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#BAE6FD')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    elements.append(pass_table)
    elements.append(Spacer(1, 14))

    # 3. CUSTOMER INFORMATION TABLE
    elements.append(Paragraph("👤 <b>Customer Details</b>", section_header_style))
    elements.append(Spacer(1, 4))

    cust_grid = [
        [Paragraph("Customer Name:", label_style), Paragraph(cust_name, val_style),
         Paragraph("Contact Mobile:", label_style), Paragraph(cust_phone, val_style)],
        [Paragraph("Email Address:", label_style), Paragraph(cust_email, val_style),
         Paragraph("Pass Status:", label_style), Paragraph("<font color='#059669'><b>CONFIRMED</b></font>", val_style)]
    ]
    cust_table = Table(cust_grid, colWidths=[100, 170, 100, 170])
    cust_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    elements.append(cust_table)
    elements.append(Spacer(1, 14))

    # 4. APPOINTMENT SUMMARY TABLE
    elements.append(Paragraph("📅 <b>Booking Summary & Schedule</b>", section_header_style))
    elements.append(Spacer(1, 4))

    app_date_str = appointment.appointment_date.strftime("%A, %d %B %Y") if hasattr(appointment.appointment_date, "strftime") else str(appointment.appointment_date)
    app_time_str = appointment.appointment_time.strftime("%I:%M %p") if hasattr(appointment.appointment_time, "strftime") else str(appointment.appointment_time)

    deposit_val = (price * deposit_pct / 100.0) if deposit_pct > 0 else 0.0
    deposit_str = f"{currency} {deposit_val:.2f} ({int(deposit_pct)}% Advance Required)" if deposit_pct > 0 else "No Advance Deposit Required (Pay at Venue)"

    summary_rows = [
        [Paragraph("<b>Service / Package</b>", label_style),
         Paragraph("<b>Staff Specialist</b>", label_style),
         Paragraph("<b>Date & Time</b>", label_style),
         Paragraph("<b>Duration</b>", label_style),
         Paragraph("<b>Total Amount</b>", label_style)],
        [Paragraph(service_name, val_style),
         Paragraph(staff_name, val_style),
         Paragraph(f"{app_date_str}<br/><b>{app_time_str}</b>", val_style),
         Paragraph(f"{duration} Mins", val_style),
         Paragraph(f"<b>{currency} {price:.2f}</b>", val_style)]
    ]
    summary_table = Table(summary_rows, colWidths=[120, 120, 150, 65, 85])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # Deposit Notice Box
    dep_data = [[Paragraph(f"💳 <b>Deposit & Payment Policy</b>: {deposit_str}", val_style)]]
    dep_table = Table(dep_data, colWidths=[540])
    dep_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF3C7') if deposit_pct > 0 else colors.HexColor('#F1F5F9')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#F59E0B') if deposit_pct > 0 else colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 6)
    ]))
    elements.append(dep_table)
    elements.append(Spacer(1, 14))

    # 5. POLICIES & VENUE INFORMATION
    elements.append(Paragraph("📋 <b>Important Appointment Policies & Guidelines</b>", section_header_style))
    elements.append(Spacer(1, 4))

    policy_text = (
        "• <b>Cancellation & Rescheduling</b>: Free cancellations or rescheduling up to 4 hours before slot time.<br/>"
        "• <b>Grace Period</b>: Please arrive 5-10 minutes prior to your slot. Arrivals 15+ minutes late may be rescheduled.<br/>"
        "• <b>Amenities</b>: Complimentary valet parking and Wi-Fi available at FC Road venue.<br/>"
        "• <b>Verification</b>: Please show this PDF pass or mobile SMS/WhatsApp receipt at front reception desk."
    )
    policy_data = [[Paragraph(policy_text, val_style)]]
    policy_table = Table(policy_data, colWidths=[540])
    policy_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('PADDING', (0, 0), (-1, -1), 8)
    ]))
    elements.append(policy_table)
    elements.append(Spacer(1, 20))

    # 6. FOOTER & TIMESTAMP
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1'), spaceAfter=8))
    ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"Thank you for choosing <b>{biz_name}</b>! • Pass generated automatically on {ts_str} • Support: {biz_phone}", footer_style))

    # Build PDF document
    doc.build(elements)

    pdf_url = f"{base_url}/static/pdfs/{filename}"
    return filepath, pdf_url

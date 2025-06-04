"""
Enhanced PDF Generator for SOP Templates - Phase 2
Converts JSON templates to professional PDFs with enhanced formatting for AI-generated content
Supports larger content, better styling, and professional branding
"""

import os
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus import Image, KeepTogether, ListFlowable, ListItem, HRFlowable
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
import qrcode
from io import BytesIO
import markdown
from PIL import Image as PILImage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedSOPPDFGenerator:
    """Enhanced PDF generator for AI-generated SOP templates with improved formatting"""

    def __init__(self, brand_config: Optional[Dict] = None):
        """
        Initialize the enhanced PDF generator

        Args:
            brand_config: Optional branding configuration dictionary
        """
        self.brand_config = brand_config or self.get_default_brand()
        self.styles = self.setup_styles()
        self.page_count = 0
        logger.info("Enhanced PDF generator initialized")

    def get_default_brand(self) -> Dict[str, Any]:
        """
        Default branding configuration optimized for professional SOPs

        Returns:
            Dictionary containing brand configuration
        """
        return {
            'primary_color': colors.HexColor('#2C3E50'),
            'secondary_color': colors.HexColor('#3498DB'),
            'accent_color': colors.HexColor('#E74C3C'),
            'success_color': colors.HexColor('#27AE60'),
            'warning_color': colors.HexColor('#F39C12'),
            'logo_path': 'designs/assets/logo.png',
            'font_family': 'Helvetica',
            'company_name': 'Professional SOP Templates',
            'tagline': 'AI-Powered Compliance Solutions',
            'footer_text': 'Generated with AI-Enhanced SOP Builder'
        }

    def setup_styles(self) -> Dict[str, ParagraphStyle]:
        """
        Setup enhanced paragraph styles optimized for AI-generated content

        Returns:
            Dictionary of paragraph styles
        """
        styles = getSampleStyleSheet()

        def add_style_if_not_exists(style_name, style_def):
            """Helper to add style only if it doesn't exist"""
            if style_name not in [s.name for s in styles.byName.values()]:
                styles.add(style_def)

        # Enhanced title style - Increased for better visibility
        add_style_if_not_exists('CustomTitle', ParagraphStyle(
            name='CustomTitle',
            parent=styles['Title'],
            fontSize=28,  # Increased from 26
            textColor=self.brand_config['primary_color'],
            spaceAfter=36,
            spaceBefore=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))

        # Subtitle style - Increased for better readability
        add_style_if_not_exists('Subtitle', ParagraphStyle(
            name='Subtitle',
            parent=styles['Normal'],
            fontSize=18,  # Increased from 16
            textColor=self.brand_config['secondary_color'],
            spaceAfter=24,
            spaceBefore=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Oblique'
        ))

        # Enhanced heading styles - Improved hierarchy and readability
        add_style_if_not_exists('CustomHeading1', ParagraphStyle(
            name='CustomHeading1',
            parent=styles['Heading1'],
            fontSize=22,  # Increased from 20
            textColor=self.brand_config['primary_color'],
            spaceAfter=18,  # Increased spacing
            spaceBefore=24,  # Increased spacing
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderPadding=0,
            leftIndent=0
        ))

        add_style_if_not_exists('CustomHeading2', ParagraphStyle(
            name='CustomHeading2',
            parent=styles['Heading2'],
            fontSize=18,  # Increased from 16
            textColor=self.brand_config['secondary_color'],
            spaceAfter=14,  # Increased spacing
            spaceBefore=18,  # Increased spacing
            fontName='Helvetica-Bold'
        ))

        add_style_if_not_exists('CustomHeading3', ParagraphStyle(
            name='CustomHeading3',
            parent=styles['Heading3'],
            fontSize=16,  # Increased from 14
            textColor=self.brand_config['primary_color'],
            spaceAfter=10,  # Increased spacing
            spaceBefore=14,  # Increased spacing
            fontName='Helvetica-Bold'
        ))

        # Enhanced body text styles - Increased for better readability
        add_style_if_not_exists('BodyText', ParagraphStyle(
            name='BodyText',
            parent=styles['Normal'],
            fontSize=12,  # Increased from 11 - standard professional size
            spaceAfter=10,  # Increased spacing
            spaceBefore=6,  # Increased spacing
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            leading=15  # Added line spacing for better readability
        ))

        # List styles - Improved for better readability
        add_style_if_not_exists('BulletList', ParagraphStyle(
            name='BulletList',
            parent=styles['Normal'],
            fontSize=12,  # Increased from 11 to match body text
            leftIndent=24,  # Increased indent for better hierarchy
            bulletIndent=12,  # Adjusted bullet position
            spaceAfter=6,  # Increased spacing
            fontName='Helvetica',
            leading=15  # Added line spacing
        ))

        add_style_if_not_exists('NumberedList', ParagraphStyle(
            name='NumberedList',
            parent=styles['Normal'],
            fontSize=12,  # Increased from 11 to match body text
            leftIndent=24,  # Increased indent for better hierarchy
            bulletIndent=12,  # Adjusted bullet position
            spaceAfter=6,  # Increased spacing
            fontName='Helvetica',
            leading=15  # Added line spacing
        ))

        # Alert and callout styles - Improved readability
        add_style_if_not_exists('Alert', ParagraphStyle(
            name='Alert',
            parent=styles['Normal'],
            fontSize=12,  # Increased from 11
            textColor=self.brand_config['accent_color'],
            leftIndent=24,
            rightIndent=24,
            spaceAfter=14,  # Increased spacing
            spaceBefore=14,  # Increased spacing
            borderColor=self.brand_config['accent_color'],
            borderWidth=1,
            borderPadding=14,  # Increased padding
            backColor=colors.HexColor('#FDF2F2'),
            fontName='Helvetica',
            leading=15  # Added line spacing
        ))

        add_style_if_not_exists('Success', ParagraphStyle(
            name='Success',
            parent=styles['Normal'],
            fontSize=12,  # Increased from 11
            textColor=self.brand_config['success_color'],
            leftIndent=24,
            rightIndent=24,
            spaceAfter=14,  # Increased spacing
            spaceBefore=14,  # Increased spacing
            borderColor=self.brand_config['success_color'],
            borderWidth=1,
            borderPadding=14,  # Increased padding
            backColor=colors.HexColor('#F0FDF4'),
            fontName='Helvetica',
            leading=15  # Added line spacing
        ))

        add_style_if_not_exists('Warning', ParagraphStyle(
            name='Warning',
            parent=styles['Normal'],
            fontSize=12,  # Increased from 11
            textColor=self.brand_config['warning_color'],
            leftIndent=24,
            rightIndent=24,
            spaceAfter=14,  # Increased spacing
            spaceBefore=14,  # Increased spacing
            borderColor=self.brand_config['warning_color'],
            borderWidth=1,
            borderPadding=14,  # Increased padding
            backColor=colors.HexColor('#FFFBEB'),
            fontName='Helvetica',
            leading=15  # Added line spacing
        ))

        # Code/procedure style - Improved readability
        add_style_if_not_exists('Code', ParagraphStyle(
            name='Code',
            parent=styles['Normal'],
            fontSize=11,  # Increased from 10 for better readability
            fontName='Courier',
            leftIndent=24,  # Increased indent
            rightIndent=24,  # Increased indent
            spaceAfter=10,  # Increased spacing
            spaceBefore=10,  # Increased spacing
            backColor=colors.HexColor('#F8F9FA'),
            borderColor=colors.HexColor('#E9ECEF'),
            borderWidth=1,
            borderPadding=12,  # Increased padding
            leading=14  # Added line spacing for code
        ))

        return styles

    def clean_html_text(self, text: str) -> str:
        """
        Clean and fix malformed HTML in text content

        Args:
            text: Text that may contain malformed HTML

        Returns:
            Cleaned text with proper HTML formatting
        """
        if not text:
            return text

        # Fix common HTML issues
        # Fix double opening tags like <b>text<b> -> <b>text</b>
        import re

        # Fix malformed bold tags
        text = re.sub(r'<b>([^<]*)<b>', r'<b>\1</b>', text)
        text = re.sub(r'<i>([^<]*)<i>', r'<i>\1</i>', text)
        text = re.sub(r'<u>([^<]*)<u>', r'<u>\1</u>', text)

        # Remove any remaining unclosed tags at end of text
        text = re.sub(r'<(b|i|u)>([^<]*?)$', r'<\1>\2</\1>', text)

        # Escape special characters that could break XML parsing
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;').replace('>', '&gt;')

        # But restore our intentional HTML tags
        text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
        text = text.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
        text = text.replace('&lt;u&gt;', '<u>').replace('&lt;/u&gt;', '</u>')

        return text

    def improve_text_readability(self, text: str) -> str:
        """
        Improve text readability by breaking up large blocks and adding proper formatting

        Args:
            text: Raw text content

        Returns:
            Improved text with better paragraph breaks and formatting
        """
        if not text:
            return text

        # Split into sentences for better paragraph breaks
        import re

        # Clean up excessive whitespace
        text = re.sub(r'\s+', ' ', text.strip())

        # Break up very long paragraphs (more than 4 sentences)
        sentences = re.split(r'(?<=[.!?])\s+', text)

        improved_lines = []
        current_paragraph = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            current_paragraph.append(sentence)

            # Break paragraph after 3-4 sentences for better readability
            if len(current_paragraph) >= 3:
                # Check if this is a good breaking point
                if (sentence.endswith('.') and
                    not sentence.endswith('etc.') and
                    not sentence.endswith('vs.') and
                    not re.search(r'\b(Mr|Mrs|Dr|Prof|Inc|Ltd|Corp)\.$', sentence)):

                    improved_lines.append(' '.join(current_paragraph))
                    improved_lines.append('')  # Empty line for paragraph break
                    current_paragraph = []

        # Add any remaining sentences
        if current_paragraph:
            improved_lines.append(' '.join(current_paragraph))

        # Join back together
        result = '\n'.join(improved_lines)

        # Clean up multiple empty lines
        result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)

        return result

    def create_header_footer(self, canvas, doc):
        """Add header and footer to each page"""
        canvas.saveState()

        # Header
        if os.path.exists(self.brand_config['logo_path']):
            logo = Image(self.brand_config['logo_path'], width=1*inch, height=0.5*inch)
            logo.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - 0.5*inch)

        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.grey)
        canvas.drawString(doc.width - 2*inch, doc.height + doc.topMargin - 0.3*inch,
                         f"Generated: {datetime.now().strftime('%B %d, %Y')}")

        # Footer
        canvas.drawString(doc.leftMargin, 0.5*inch,
                         f"© {datetime.now().year} {self.brand_config['company_name']}")
        canvas.drawRightString(doc.width + doc.leftMargin, 0.5*inch,
                              f"Page {doc.page}")

        canvas.restoreState()

    def generate_qr_code(self, data):
        """Generate QR code image"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to reportlab-compatible format
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return Image(buffer, width=1.5*inch, height=1.5*inch)

    def enhanced_markdown_to_flowables(self, md_text: str) -> List[Any]:
        """
        Enhanced markdown to flowables converter for AI-generated content with improved readability

        Args:
            md_text: Markdown text to convert

        Returns:
            List of reportlab flowables
        """
        if not md_text or not md_text.strip():
            return []

        flowables = []

        # Pre-process text to improve readability
        md_text = self.improve_text_readability(md_text)

        lines = md_text.split('\n')
        i = 0
        current_paragraph = []

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                # Empty line - finish current paragraph if any
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))  # Add space after paragraph
                    current_paragraph = []
                i += 1
                continue

            # Handle headers
            if line.startswith('# '):
                # Finish current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))
                    current_paragraph = []

                text = line[2:].strip()
                flowables.append(Spacer(1, 16))  # Extra space before major headings
                flowables.append(Paragraph(self.clean_html_text(text), self.styles['CustomHeading1']))
                flowables.append(Spacer(1, 12))

            elif line.startswith('## '):
                # Finish current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))
                    current_paragraph = []

                text = line[3:].strip()
                flowables.append(Spacer(1, 12))  # Space before section headings
                flowables.append(Paragraph(self.clean_html_text(text), self.styles['CustomHeading2']))
                flowables.append(Spacer(1, 8))

            elif line.startswith('### '):
                # Finish current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))
                    current_paragraph = []

                text = line[4:].strip()
                flowables.append(Spacer(1, 8))  # Space before subsection headings
                flowables.append(Paragraph(self.clean_html_text(text), self.styles['CustomHeading3']))
                flowables.append(Spacer(1, 6))

            # Handle bullet lists
            elif line.startswith('- ') or line.startswith('* '):
                # Finish current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))
                    current_paragraph = []

                list_items = []
                while i < len(lines) and (lines[i].strip().startswith('- ') or lines[i].strip().startswith('* ')):
                    item_text = lines[i].strip()[2:].strip()
                    list_items.append(item_text)
                    i += 1
                i -= 1  # Adjust for the outer loop increment

                for item in list_items:
                    flowables.append(Paragraph(self.clean_html_text(f"• {item}"), self.styles['BulletList']))
                flowables.append(Spacer(1, 8))

            # Handle numbered lists
            elif re.match(r'^\d+\.\s', line):
                # Finish current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))
                    current_paragraph = []

                list_items = []
                while i < len(lines) and re.match(r'^\d+\.\s', lines[i].strip()):
                    item_text = re.sub(r'^\d+\.\s', '', lines[i].strip())
                    list_items.append(item_text)
                    i += 1
                i -= 1  # Adjust for the outer loop increment

                for idx, item in enumerate(list_items, 1):
                    flowables.append(Paragraph(self.clean_html_text(f"{idx}. {item}"), self.styles['NumberedList']))
                flowables.append(Spacer(1, 8))

            # Handle special callouts
            elif line.startswith('**Important:**') or line.startswith('**Note:**'):
                # Finish current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))
                    current_paragraph = []

                text = line.replace('**Important:**', '').replace('**Note:**', '').strip()
                flowables.append(Paragraph(self.clean_html_text(f"📌 {text}"), self.styles['Alert']))
                flowables.append(Spacer(1, 8))

            elif line.startswith('**Warning:**'):
                # Finish current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))
                    current_paragraph = []

                text = line.replace('**Warning:**', '').strip()
                flowables.append(Paragraph(self.clean_html_text(f"⚠️ {text}"), self.styles['Warning']))
                flowables.append(Spacer(1, 8))

            elif line.startswith('**Success:**') or line.startswith('**Best Practice:**'):
                # Finish current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))
                    current_paragraph = []

                text = line.replace('**Success:**', '').replace('**Best Practice:**', '').strip()
                flowables.append(Paragraph(self.clean_html_text(f"✅ {text}"), self.styles['Success']))
                flowables.append(Spacer(1, 8))

            # Handle code blocks
            elif line.startswith('```'):
                # Finish current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
                    flowables.append(Spacer(1, 8))
                    current_paragraph = []

                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1

                if code_lines:
                    code_text = '\n'.join(code_lines)
                    flowables.append(Paragraph(code_text, self.styles['Code']))
                    flowables.append(Spacer(1, 8))

            # Regular paragraph text - accumulate into current paragraph
            else:
                if line:  # Only add non-empty lines
                    current_paragraph.append(line)

            i += 1

        # Handle any remaining paragraph content
        if current_paragraph:
            para_text = ' '.join(current_paragraph)
            flowables.append(Paragraph(self.clean_html_text(para_text), self.styles['BodyText']))
            flowables.append(Spacer(1, 8))

        return flowables

    def create_checklist_table(self, items):
        """Create a checklist table"""
        data = []
        for item in items:
            data.append(['☐', item])

        table = Table(data, colWidths=[0.3*inch, 5*inch])
        table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        return table

    def generate_enhanced_pdf(self, template_data: Dict, output_path: str) -> str:
        """
        Generate enhanced PDF from AI-generated template data

        Args:
            template_data: Dictionary containing template data
            output_path: Path where PDF should be saved

        Returns:
            Path to generated PDF file
        """
        logger.info(f"Generating enhanced PDF: {output_path}")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=60,  # Reduced margins for more content space
            leftMargin=60,   # Reduced margins for more content space
            topMargin=120,   # Increased to prevent header overlap
            bottomMargin=72
        )

        # Build content
        story = []

        # Enhanced title page
        template_type = template_data.get('metadata', {}).get('type', 'Unknown')
        story.append(Paragraph(
            f"{template_type.replace('-', ' ').title()} SOP Template",
            self.styles['CustomTitle']
        ))

        story.append(Paragraph(
            self.brand_config['tagline'],
            self.styles['Subtitle']
        ))

        story.append(Spacer(1, 0.3*inch))

        # Add generation info
        generation_method = template_data.get('metadata', {}).get('generation_method', 'unknown')
        if generation_method == 'ai_generated':
            story.append(Paragraph(
                "✨ Generated with Advanced AI Technology",
                self.styles['Success']
            ))

        story.append(Spacer(1, 0.4*inch))

        # Enhanced metadata table
        metadata = [
            ['Version:', template_data.get('metadata', {}).get('version', '1.0')],
            ['Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')],
            ['Template Type:', template_type.replace('-', ' ').title()],
            ['Compliance Standards:', ', '.join(template_data.get('metadata', {}).get('compliance_standards', []))],
        ]

        # Add generation stats if available
        stats = template_data.get('generation_stats', {})
        if stats:
            metadata.extend([
                ['Sections Generated:', f"{stats.get('successful_sections', 0)}/{stats.get('total_sections', 0)}"],
                ['Generation Time:', f"{stats.get('generation_time_seconds', 0):.1f} seconds"],
                ['AI Provider Used:', 'Multiple Free LLM Providers' if generation_method == 'ai_generated' else 'Hardcoded Content']
            ])

        metadata_table = Table(metadata, colWidths=[2.4*inch, 4.0*inch])  # Adjusted for wider margins
        metadata_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 11),  # Increased from 10
            ('TEXTCOLOR', (0, 0), (0, -1), self.brand_config['primary_color']),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),  # Increased padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),  # Increased padding
            ('TOPPADDING', (0, 0), (-1, -1), 6),   # Increased padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6), # Increased padding
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.lightgrey),
        ]))

        story.append(metadata_table)
        story.append(Spacer(1, 0.3*inch))

        # Add quality indicators
        if generation_method == 'ai_generated':
            story.append(Paragraph(
                "🎯 This SOP template has been generated using advanced AI technology with industry-specific knowledge and regulatory compliance features.",
                self.styles['Alert']
            ))

        story.append(PageBreak())

        # Enhanced table of contents with automatic page numbering
        story.append(Paragraph("Table of Contents", self.styles['CustomHeading1']))
        story.append(Spacer(1, 0.2*inch))

        # Create a proper Table of Contents with automatic page numbering
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(
                name='TOCLevel0',
                fontName='Helvetica',
                fontSize=12,
                leading=16,
                leftIndent=0,
                firstLineIndent=0,
                spaceBefore=6,
                spaceAfter=6,
            ),
        ]

        # Add TOC to story
        story.append(toc)
        story.append(Spacer(1, 0.3*inch))

        # Add legend
        legend_text = "Legend: ✅ Successfully Generated | ⚠️ Fallback Content | 💾 From Cache"
        story.append(Paragraph(legend_text, self.styles['BodyText']))
        story.append(PageBreak())

        # Add sections with enhanced formatting and TOC entries
        sections = template_data.get('sections', {})
        for section_name, section_data in sorted(
            sections.items(),
            key=lambda x: x[1].get('order', 999)
        ):
            # Section header with status
            status_text = ""
            if section_data.get('error'):
                status_text = " (Fallback Content)"
            elif section_data.get('cached', False):
                status_text = " (Cached)"

            # Create section header with TOC entry
            section_title = f"{section_name.replace('_', ' ').title()}{status_text}"
            section_para = Paragraph(section_title, self.styles['CustomHeading1'])

            # Add TOC entry for this section
            toc.addEntry(0, section_title, 1)

            story.append(section_para)
            story.append(Spacer(1, 0.2*inch))

            # Add generation timestamp
            if section_data.get('generated_at'):
                gen_time = section_data['generated_at']
                story.append(Paragraph(
                    f"Generated: {gen_time}",
                    self.styles['BodyText']
                ))
                story.append(Spacer(1, 0.1*inch))

            # Section content using enhanced markdown processor
            content = section_data.get('content', '')
            if content:
                content_flowables = self.enhanced_markdown_to_flowables(content)
                story.extend(content_flowables)
            else:
                story.append(Paragraph("No content available for this section.", self.styles['BodyText']))

            # Add checklist if available
            if 'checklist_items' in section_data:
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph("Checklist", self.styles['CustomHeading2']))
                story.append(Spacer(1, 0.1*inch))
                story.append(self.create_checklist_table(section_data['checklist_items']))

            story.append(PageBreak())

        # Add enhanced compliance features section
        compliance_features = template_data.get('compliance_features', {})
        if compliance_features:
            story.append(Paragraph("Compliance & Regulatory Features", self.styles['CustomHeading1']))
            story.append(Spacer(1, 0.2*inch))

            # Add audit trail info
            if compliance_features.get('audit_trail', {}).get('enabled'):
                story.append(Paragraph("Audit Trail", self.styles['CustomHeading2']))
                story.append(Paragraph(
                    "✅ This template includes comprehensive audit trail capabilities for tracking all changes and access.",
                    self.styles['Success']
                ))
                story.append(Spacer(1, 0.1*inch))

            # Add version control info
            if compliance_features.get('version_control', {}).get('enabled'):
                story.append(Paragraph("Version Control", self.styles['CustomHeading2']))
                story.append(Paragraph(
                    "📋 Automatic version control ensures all changes are tracked and documented.",
                    self.styles['Alert']
                ))
                story.append(Spacer(1, 0.1*inch))

            # Add QR codes for regulatory links
            regulatory_links = compliance_features.get('regulatory_links', {})
            if regulatory_links:
                story.append(Paragraph("Regulatory Resources", self.styles['CustomHeading2']))
                for name, url in regulatory_links.items():
                    try:
                        qr_image = self.generate_qr_code(url)
                        story.append(Paragraph(f"{name} Requirements", self.styles['CustomHeading3']))
                        story.append(qr_image)
                        story.append(Paragraph(
                            f"Scan QR code to access the latest {name} requirements and updates.",
                            self.styles['BodyText']
                        ))
                        story.append(Spacer(1, 0.2*inch))
                    except Exception as e:
                        logger.warning(f"Failed to generate QR code for {name}: {e}")
                        story.append(Paragraph(f"{name}: {url}", self.styles['BodyText']))

        # Add footer with generation summary
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("Document Summary", self.styles['CustomHeading2']))

        summary_data = [
            ['Total Sections:', str(stats.get('total_sections', 0))],
            ['Successfully Generated:', str(stats.get('successful_sections', 0))],
            ['From Cache:', str(stats.get('cached_sections', 0))],
            ['Generation Method:', 'AI-Generated' if generation_method == 'ai_generated' else 'Hardcoded'],
            ['Document Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')]
        ]

        summary_table = Table(summary_data, colWidths=[2.8*inch, 3.6*inch])  # Adjusted for wider margins
        summary_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 11),  # Increased from 9
            ('TEXTCOLOR', (0, 0), (0, -1), self.brand_config['primary_color']),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),  # Increased padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),  # Increased padding
            ('TOPPADDING', (0, 0), (-1, -1), 6),   # Added top padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6), # Added bottom padding
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))

        story.append(summary_table)

        # Build PDF with enhanced header/footer using multiBuild for TOC
        try:
            doc.multiBuild(story, onFirstPage=self.create_enhanced_header_footer,
                          onLaterPages=self.create_enhanced_header_footer)
            logger.info(f"PDF successfully generated: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error building PDF: {e}")
            raise

    def create_enhanced_header_footer(self, canvas, doc):
        """
        Enhanced header and footer for AI-generated content

        Args:
            canvas: ReportLab canvas object
            doc: Document object
        """
        canvas.saveState()

        # Enhanced header - Fixed positioning to prevent overlap
        # Position header in the top margin area, well above content
        header_y = doc.height + doc.topMargin - 30  # Fixed positioning

        # Logo (if exists)
        logo_path = self.brand_config.get('logo_path', '')
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image(logo_path, width=0.8*inch, height=0.4*inch)  # Smaller logo
                logo.drawOn(canvas, doc.leftMargin, header_y - 10)
            except Exception as e:
                logger.warning(f"Could not load logo: {e}")

        # Company name and tagline - Improved positioning
        canvas.setFont('Helvetica-Bold', 12)  # Slightly smaller for header
        canvas.setFillColor(self.brand_config['primary_color'])
        canvas.drawString(doc.leftMargin + 1.0*inch, header_y,
                         self.brand_config['company_name'])

        canvas.setFont('Helvetica', 9)  # Smaller tagline
        canvas.setFillColor(self.brand_config['secondary_color'])
        canvas.drawString(doc.leftMargin + 1.0*inch, header_y - 15,
                         self.brand_config['tagline'])

        # Generation date - Right aligned in header
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(doc.width + doc.leftMargin, header_y,
                              f"Generated: {datetime.now().strftime('%B %d, %Y')}")

        # Page number - Right aligned below date
        canvas.setFont('Helvetica', 9)
        canvas.drawRightString(doc.width + doc.leftMargin, header_y - 15,
                              f"Page {doc.page}")

        # Header line - Positioned to separate header from content
        canvas.setStrokeColor(self.brand_config['primary_color'])
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, header_y - 25,
                   doc.width + doc.leftMargin, header_y - 25)

        # Enhanced footer - Improved positioning and spacing
        footer_y = 40  # Fixed position from bottom

        # Footer line - Positioned above footer text
        canvas.setStrokeColor(self.brand_config['primary_color'])
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, footer_y + 15,
                   doc.width + doc.leftMargin, footer_y + 15)

        # Copyright and branding - Left aligned
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.grey)
        canvas.drawString(doc.leftMargin, footer_y,
                         f"© {datetime.now().year} {self.brand_config['company_name']}")

        # Footer text - Right aligned
        canvas.setFont('Helvetica', 9)
        footer_text = self.brand_config.get('footer_text', 'Professional SOP Templates')
        canvas.drawRightString(doc.width + doc.leftMargin, footer_y,
                              footer_text)

        canvas.restoreState()

    # Backward compatibility method
    def generate_pdf(self, template_data: Dict, output_path: str) -> str:
        """
        Backward compatibility wrapper for generate_enhanced_pdf

        Args:
            template_data: Template data dictionary
            output_path: Output file path

        Returns:
            Path to generated PDF
        """
        return self.generate_enhanced_pdf(template_data, output_path)


def main():
    """Convert JSON template to PDF"""
    import argparse

    parser = argparse.ArgumentParser(description='Convert SOP template to PDF')
    parser.add_argument('--input', required=True, help='Input JSON file')
    parser.add_argument('--output', help='Output PDF file')
    parser.add_argument('--brand-config', help='Brand configuration JSON file')

    args = parser.parse_args()

    # Load template data
    with open(args.input, 'r') as f:
        template_data = json.load(f)

    # Load brand config if provided
    brand_config = None
    if args.brand_config:
        with open(args.brand_config, 'r') as f:
            brand_config = json.load(f)

    # Generate output path if not provided
    if not args.output:
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        args.output = f"outputs/pdfs/{base_name}.pdf"

    # Create enhanced generator and build PDF
    try:
        generator = EnhancedSOPPDFGenerator(brand_config)
        output_path = generator.generate_enhanced_pdf(template_data, args.output)

        print(f"✅ Enhanced PDF generated successfully!")
        print(f"📁 Output file: {output_path}")

        # Print file size
        file_size = os.path.getsize(output_path)
        print(f"📊 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")

    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        logger.error(f"PDF generation failed: {e}")
        raise


if __name__ == "__main__":
    main()

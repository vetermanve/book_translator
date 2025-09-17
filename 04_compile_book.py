#!/usr/bin/env python3

import json
import os
from pathlib import Path
from datetime import datetime
from lxml import etree
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
import base64


class FinalCompilerWithFigures:
    """Финальный компилятор с векторными диаграммами"""
    
    def __init__(self, translations_dir="translations", figures_dir="figures", use_filtered=False):
        # Если use_filtered=True, используем отфильтрованные переводы
        if use_filtered and Path("translations_filtered").exists():
            self.translations_dir = Path("translations_filtered")
            print("📋 Используем отфильтрованные переводы из translations_filtered")
        else:
            self.translations_dir = Path(translations_dir)
        
        self.figures_dir = Path(figures_dir)
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
        
        # Загружаем метаданные диаграмм
        self.figures_metadata = self._load_figures_metadata()
        
        # Регистрируем шрифты
        self._register_fonts()
    
    def _load_figures_metadata(self):
        """Загружает метаданные диаграмм"""
        metadata_file = self.figures_dir / "figures_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"figures": []}
    
    def _register_fonts(self):
        """Регистрирует шрифты с поддержкой русского языка"""
        try:
            font_paths = [
                "/Library/Fonts/Arial Unicode.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        font_name = Path(font_path).stem
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                        self.font_name = font_name
                        print(f"✅ Используется шрифт: {font_name}")
                        break
                    except:
                        continue
            else:
                self.font_name = 'Helvetica'
        except:
            self.font_name = 'Helvetica'
    
    def compile_pdf_with_figures(self, book_title="CMMI для разработки v1.3", author="SEI"):
        """Компилирует PDF с векторными диаграммами"""
        
        output_file = self.output_dir / f"{book_title} (Полная версия).pdf"
        
        doc = SimpleDocTemplate(
            str(output_file),
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        story = []
        styles = self._get_styles()
        
        # Титульная страница
        story.append(Paragraph(book_title, styles['CustomTitle']))
        story.append(Spacer(1, 12))
        story.append(Paragraph(author, styles['CustomAuthor']))
        story.append(PageBreak())
        
        # Создаем карту диаграмм по страницам
        figures_by_page = {}
        for fig in self.figures_metadata.get("figures", []):
            page = fig["page"]
            if page not in figures_by_page:
                figures_by_page[page] = []
            figures_by_page[page].append(fig)
        
        # Отслеживаем какие диаграммы уже вставлены (глобально для всей книги)
        # Используем комбинацию типа и ID для уникальности
        inserted_figures_global = set()
        
        # Обрабатываем главы
        chapters = sorted(self.translations_dir.glob("chapter_*_translated.json"))
        
        # Загружаем метаданные извлеченных глав для соответствия страниц
        extracted_metadata_file = self.output_dir.parent / "extracted_fixed" / "metadata.json"
        page_mapping = {}
        if extracted_metadata_file.exists():
            with open(extracted_metadata_file, 'r', encoding='utf-8') as f:
                extracted_meta = json.load(f)
                for chapter_info in extracted_meta.get("chapters", []):
                    chapter_num = chapter_info["number"]
                    page_mapping[chapter_num] = {
                        "start": chapter_info.get("start_page", 0),
                        "end": chapter_info.get("end_page", 0)
                    }
        
        for chapter_file in chapters:
            with open(chapter_file, 'r', encoding='utf-8') as f:
                chapter_data = json.load(f)
            
            chapter_num = chapter_data.get("number", 0)
            
            # Заголовок главы
            chapter_title = chapter_data.get("title", f"Глава {chapter_num}")
            story.append(Paragraph(chapter_title, styles['CustomHeading']))
            story.append(Spacer(1, 12))
            
            # Определяем реальные страницы для этой главы
            if chapter_num in page_mapping:
                start_page = page_mapping[chapter_num]["start"]
                end_page = page_mapping[chapter_num]["end"]
            else:
                # Fallback: оценка на основе номера главы
                start_page = chapter_num * 3
                end_page = start_page + 3
            
            # Проверяем, есть ли диаграммы для этого диапазона страниц
            # Расширяем диапазон на 3 страницы в обе стороны для лучшего покрытия
            chapter_figures = []
            for page in range(max(0, start_page - 3), end_page + 5):
                if page in figures_by_page:
                    for fig in figures_by_page[page]:
                        # Вставляем только если еще не вставляли эту диаграмму
                        # Используем комбинацию типа и ID для уникальности
                        fig_key = f"{fig['type']}_{fig['id']}"
                        if fig_key not in inserted_figures_global:
                            chapter_figures.append(fig)
                            inserted_figures_global.add(fig_key)
            
            # Вставляем найденные диаграммы в начало главы
            for fig in chapter_figures:
                figure_element = self._create_figure_element(fig, styles)
                if figure_element:
                    story.append(Spacer(1, 12))
                    story.append(figure_element)
                    story.append(Spacer(1, 12))
                    print(f"  📊 Вставлена {fig['type']} {fig['id']} в главу {chapter_num} (стр. {fig['page']+1})")
            
            # Обрабатываем параграфы главы
            for paragraph in chapter_data.get("paragraphs", []):
                if not paragraph:
                    story.append(Spacer(1, 12))
                    continue
                
                try:
                    safe_paragraph = self._escape_xml(paragraph)
                    story.append(Paragraph(safe_paragraph, styles['CustomNormal']))
                    story.append(Spacer(1, 6))
                except:
                    continue
            
            story.append(PageBreak())
        
        # Собираем документ
        doc.build(story)
        print(f"✅ PDF с диаграммами создан: {output_file}")
        return output_file
    
    def _create_figure_element(self, figure_info, styles):
        """Создает элемент диаграммы для PDF"""
        
        figure_path = self.figures_dir / figure_info["filename"]
        
        if not figure_path.exists():
            return None
        
        try:
            # Открываем изображение
            img = Image.open(figure_path)
            width, height = img.size
            
            # Масштабируем для PDF
            max_width = 450
            max_height = 600
            
            scale = min(max_width/width, max_height/height, 1.0)
            
            elements = []
            
            # Изображение
            rl_image = RLImage(str(figure_path), 
                             width=width*scale, 
                             height=height*scale)
            elements.append(rl_image)
            
            # Подпись к диаграмме
            caption = figure_info.get("caption", "")
            if not caption and figure_info.get("id"):
                caption = f"{figure_info['type'].capitalize()} {figure_info['id']}"
            
            if caption:
                elements.append(Spacer(1, 6))
                elements.append(Paragraph(f"<i>{caption}</i>", styles['Caption']))
            
            # Возвращаем как единый блок
            return KeepTogether(elements)
            
        except Exception as e:
            print(f"⚠️ Не удалось добавить диаграмму {figure_info['filename']}: {e}")
            return None
    
    def _get_styles(self):
        """Создает стили для PDF"""
        styles = getSampleStyleSheet()
        
        styles.add(ParagraphStyle(
            name='CustomNormal',
            fontName=self.font_name,
            fontSize=11,
            leading=16,
            spaceBefore=6,
            spaceAfter=6,
            firstLineIndent=15,
            alignment=TA_JUSTIFY
        ))
        
        styles.add(ParagraphStyle(
            name='CustomHeading',
            fontName=self.font_name,
            fontSize=14,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
            alignment=TA_CENTER
        ))
        
        styles.add(ParagraphStyle(
            name='CustomTitle',
            fontName=self.font_name,
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=20
        ))
        
        styles.add(ParagraphStyle(
            name='CustomAuthor',
            fontName=self.font_name,
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=20
        ))
        
        styles.add(ParagraphStyle(
            name='Caption',
            fontName=self.font_name,
            fontSize=10,
            alignment=TA_CENTER,
            textColor='#555555',
            spaceBefore=3,
            spaceAfter=3
        ))
        
        return styles
    
    def _escape_xml(self, text):
        """Экранирует специальные символы для XML"""
        if not text:
            return ""
        
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        
        import re
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
        
        return text


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Компиляция финальной книги')
    parser.add_argument('--use-filtered', action='store_true',
                       help='Использовать отфильтрованные переводы из translations_filtered')
    parser.add_argument('--translations-dir', default='translations',
                       help='Директория с переводами (по умолчанию: translations)')
    
    args = parser.parse_args()
    
    print("📚 Компиляция финальной книги с векторными диаграммами...")
    print("")
    
    # Проверяем наличие отфильтрованных переводов
    if args.use_filtered or Path("translations_filtered").exists():
        if Path("translations_filtered").exists():
            print("📋 Найдены отфильтрованные переводы")
            use_filtered_choice = args.use_filtered
            if not args.use_filtered:
                response = input("   Использовать их? (y/n) [y]: ").strip().lower()
                use_filtered_choice = response != 'n'
        else:
            use_filtered_choice = False
            print("⚠️ Директория translations_filtered не найдена")
    else:
        use_filtered_choice = False
    
    compiler = FinalCompilerWithFigures(
        translations_dir=args.translations_dir,
        use_filtered=use_filtered_choice
    )
    
    # Компилируем PDF
    pdf_file = compiler.compile_pdf_with_figures(
        book_title="CMMI для разработки v1.3",
        author="Software Engineering Institute"
    )
    
    print("\n✨ Готово!")
    print(f"📖 Финальная книга: {pdf_file}")
    print("\nКнига содержит:")
    print("  • Переведенный текст")
    if use_filtered_choice:
        print("  • Отфильтрованный контент (без черного списка)")
    print("  • Все векторные диаграммы (Figure, Table)")
    print("  • Правильное форматирование")
    print("  • Поддержку русского языка")
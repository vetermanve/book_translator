#!/usr/bin/env python3

import fitz
import json
import re
from pathlib import Path
from tqdm import tqdm


class VectorFigureExtractor:
    """Извлекает векторные диаграммы из PDF как изображения высокого качества"""
    
    def __init__(self, pdf_path, output_dir="figures"):
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def extract_all_figures(self):
        """Извлекает все страницы с векторными диаграммами"""
        
        print("📖 Открываем PDF для извлечения векторных диаграмм...")
        doc = fitz.open(self.pdf_path)
        
        figures = []
        
        # Паттерны для поиска подписей к рисункам
        figure_patterns = [
            (r"Figure\s+(\d+\.\d+)", "figure"),
            (r"Table\s+(\d+\.\d+)", "table"),
        ]
        
        print("🔍 Ищем страницы с диаграммами...")
        
        for page_num in tqdm(range(len(doc)), desc="Анализ страниц"):
            page = doc[page_num]
            
            # Проверяем наличие векторных элементов
            drawings = page.get_drawings()
            
            # Если есть достаточно векторных элементов - это может быть диаграмма
            if len(drawings) > 10:  # Порог для определения диаграммы
                
                # Ищем подпись к рисунку на странице
                text = page.get_text()
                caption = None
                figure_id = None
                figure_type = "diagram"
                
                for pattern, ftype in figure_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        figure_id = match.group(1)
                        figure_type = ftype
                        
                        # Ищем полную подпись
                        lines = text.split('\n')
                        for i, line in enumerate(lines):
                            if match.group() in line:
                                # Берем текущую строку и следующую для полной подписи
                                caption = line.strip()
                                if i + 1 < len(lines) and not re.match(r'^(Figure|Table)', lines[i + 1]):
                                    next_line = lines[i + 1].strip()
                                    if next_line and len(next_line) < 100:
                                        caption = f"{caption} {next_line}"
                                break
                        break
                
                if figure_id:
                    # Извлекаем область с диаграммой
                    figure_info = self._extract_figure_region(page, page_num, figure_id, figure_type, caption)
                    if figure_info:
                        figures.append(figure_info)
                        print(f"  ✅ Извлечена {figure_type} {figure_id}: {caption[:50] if caption else ''}")
        
        doc.close()
        
        # Сохраняем метаданные
        metadata = {
            "total_figures": len(figures),
            "figures": figures
        }
        
        metadata_file = self.output_dir / "figures_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"\n✨ Извлечено {len(figures)} диаграмм")
        print(f"💾 Сохранены в папке {self.output_dir}/")
        
        return figures
    
    def _extract_figure_region(self, page, page_num, figure_id, figure_type, caption):
        """Извлекает область страницы с диаграммой"""
        
        # Определяем область диаграммы на основе векторных элементов
        drawings = page.get_drawings()
        
        if not drawings:
            return None
        
        # Находим границы всех векторных элементов
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for drawing in drawings:
            rect = drawing.get('rect', None)
            if rect:
                min_x = min(min_x, rect.x0)
                min_y = min(min_y, rect.y0)
                max_x = max(max_x, rect.x1)
                max_y = max(max_y, rect.y1)
        
        # Если нашли границы, извлекаем эту область
        if min_x < float('inf'):
            # Добавляем отступы
            padding = 20
            clip_rect = fitz.Rect(
                max(0, min_x - padding),
                max(0, min_y - padding),
                min(page.rect.width, max_x + padding),
                min(page.rect.height, max_y + padding)
            )
            
            # Извлекаем область как изображение высокого качества
            mat = fitz.Matrix(2, 2)  # Увеличение в 2 раза для лучшего качества
            pix = page.get_pixmap(matrix=mat, clip=clip_rect, alpha=False)
            
            # Сохраняем изображение
            filename = f"{figure_type}_{figure_id.replace('.', '_')}_p{page_num:03d}.png"
            filepath = self.output_dir / filename
            pix.save(str(filepath))
            
            return {
                "id": figure_id,
                "type": figure_type,
                "page": page_num,
                "caption": caption,
                "filename": filename,
                "width": pix.width,
                "height": pix.height,
                "vector_count": len(drawings)
            }
        
        # Если не можем определить границы, сохраняем всю страницу
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        filename = f"{figure_type}_{figure_id.replace('.', '_')}_p{page_num:03d}_full.png"
        filepath = self.output_dir / filename
        pix.save(str(filepath))
        
        return {
            "id": figure_id,
            "type": figure_type,
            "page": page_num,
            "caption": caption,
            "filename": filename,
            "width": pix.width,
            "height": pix.height,
            "vector_count": len(drawings),
            "full_page": True
        }
    
    def extract_specific_pages_with_many_vectors(self, min_vectors=30):
        """Извлекает страницы с большим количеством векторных элементов"""
        
        print(f"📖 Ищем страницы с {min_vectors}+ векторными элементами...")
        doc = fitz.open(self.pdf_path)
        
        complex_pages = []
        
        for page_num in tqdm(range(len(doc)), desc="Анализ"):
            page = doc[page_num]
            drawings = page.get_drawings()
            
            if len(drawings) >= min_vectors:
                print(f"  📊 Страница {page_num + 1}: {len(drawings)} векторных элементов")
                
                # Сохраняем как изображение
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                filename = f"complex_diagram_p{page_num:03d}.png"
                filepath = self.output_dir / filename
                pix.save(str(filepath))
                
                complex_pages.append({
                    "page": page_num,
                    "vector_count": len(drawings),
                    "filename": filename
                })
        
        doc.close()
        
        print(f"✅ Найдено {len(complex_pages)} сложных диаграмм")
        return complex_pages


if __name__ == "__main__":
    extractor = VectorFigureExtractor("book.pdf")
    
    print("=" * 60)
    print("ИЗВЛЕЧЕНИЕ ВЕКТОРНЫХ ДИАГРАММ")
    print("=" * 60)
    
    # Извлекаем все фигуры с подписями
    figures = extractor.extract_all_figures()
    
    print("\n📋 Извлеченные диаграммы:")
    for fig in figures[:10]:
        print(f"  {fig['type'].capitalize()} {fig['id']}: {fig['caption'][:60] if fig['caption'] else 'Без подписи'}")
        print(f"    └─ Файл: {fig['filename']} ({fig['vector_count']} векторов)")
    
    # Также ищем страницы со сложными диаграммами
    print("\n" + "=" * 60)
    print("ПОИСК СЛОЖНЫХ ДИАГРАММ")
    print("=" * 60)
    complex_pages = extractor.extract_specific_pages_with_many_vectors(min_vectors=50)
    
    print("\n✨ Готово! Все диаграммы сохранены в папке figures/")
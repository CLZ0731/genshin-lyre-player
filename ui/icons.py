import math
from PyQt5.QtCore import Qt, QSize, QRectF
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPen, QBrush, QColor, QPainterPath

class IconFactory:
    """
    自繪向量圖示工廠類別。
    使用 QPainter 在透明背景的 QPixmap 上直接繪製極簡的扁平向量圖示。
    這保證了 100% 離線可用、解析度無損、無版權問題，並完美契合 Uber Move 風格。
    包含 4x 多倍率抗鋸齒渲染，解決 High DPI 螢幕（如 4K 螢幕、125%/150%/200% 縮放）下模糊的問題。
    """
    
    @staticmethod
    def create_icon(icon_type: str, color: QColor = QColor(0, 0, 0), size: int = 24) -> QIcon:
        scale = 4.0
        draw_size = int(size * scale)
        pixmap = QPixmap(draw_size, draw_size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 縮放繪圖矩陣，使我們能用邏輯像素 (0 ~ size) 繪製，同時在實體 Pixmap 上得到 4 倍的高畫質細節
        painter.scale(scale, scale)
        
        # 設置畫筆樣式 (邏輯寬度為 2.0，縮放後實體寬度為 8.0)
        pen = QPen(color)
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        
        brush = QBrush(color)
        
        if icon_type == "plus":
            # ➕ 加號
            margin = size * 0.28
            painter.drawLine(int(margin), int(size/2), int(size - margin), int(size/2))
            painter.drawLine(int(size/2), int(margin), int(size/2), int(size - margin))
            
        elif icon_type == "transcribe":
            # 🎙️ 麥克風 (轉錄)
            w = size * 0.28
            h = size * 0.44
            x = (size - w) / 2
            y = size * 0.16
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(x, y, w, h), float(w/2), float(w/2))
            
            # 麥克風底部弧線
            cup_w = size * 0.48
            cup_x = (size - cup_w) / 2
            cup_y = size * 0.28
            painter.drawArc(QRectF(cup_x, cup_y, cup_w, cup_w), -150 * 16, 120 * 16)
            
            # 立柱與底座
            painter.drawLine(int(size/2), int(cup_y + cup_w), int(size/2), int(size * 0.84))
            base_margin = size * 0.32
            painter.drawLine(int(base_margin), int(size * 0.84), int(size - base_margin), int(size * 0.84))
            
        elif icon_type == "delete":
            # 🗑️ 垃圾桶 (刪除)
            margin_x = size * 0.28
            margin_y = size * 0.2
            
            # 垃圾桶蓋子橫線
            painter.drawLine(int(margin_x - 3), int(margin_y + 4), int(size - margin_x + 3), int(margin_y + 4))
            
            # 蓋子把手
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(size/2 - 3, margin_y, 6, 4))
            
            # 垃圾桶桶身
            painter.drawRect(QRectF(margin_x, margin_y + 4, size - 2*margin_x, size - 2*margin_y - 4))
            
            # 桶身內部條紋
            painter.drawLine(int(size/2 - 2), int(margin_y + 8), int(size/2 - 2), int(size - margin_y - 4))
            painter.drawLine(int(size/2 + 2), int(margin_y + 8), int(size/2 + 2), int(size - margin_y - 4))
            
        elif icon_type == "gear":
            # ⚙️ 齒輪 (設定)
            painter.setBrush(Qt.NoBrush)
            # 外圓
            r_outer = size * 0.26
            painter.drawEllipse(QRectF(size/2 - r_outer, size/2 - r_outer, 2*r_outer, 2*r_outer))
            # 內圓
            r_inner = size * 0.1
            painter.drawEllipse(QRectF(size/2 - r_inner, size/2 - r_inner, 2*r_inner, 2*r_inner))
            # 齒牙
            for i in range(8):
                angle = i * (2 * math.pi / 8)
                x1 = size/2 + r_outer * math.cos(angle)
                y1 = size/2 + r_outer * math.sin(angle)
                x2 = size/2 + (r_outer + 3) * math.cos(angle)
                y2 = size/2 + (r_outer + 3) * math.sin(angle)
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                
        elif icon_type == "minimize":
            # ─ 最小化 (減號)
            margin = size * 0.25
            painter.drawLine(int(margin), int(size/2), int(size - margin), int(size/2))
            
        elif icon_type == "close":
            # ✕ 關閉 (叉號)
            margin = size * 0.3
            painter.drawLine(int(margin), int(margin), int(size - margin), int(size - margin))
            painter.drawLine(int(size - margin), int(margin), int(margin), int(size - margin))
            
        elif icon_type == "play":
            # ▶ 播放三角形 (實心)
            painter.setBrush(brush)
            path = QPainterPath()
            margin_x = size * 0.34
            margin_y = size * 0.28
            path.moveTo(margin_x, margin_y)
            path.lineTo(size - margin_x + 2, size / 2)
            path.lineTo(margin_x, size - margin_y)
            path.closeSubpath()
            painter.drawPath(path)
            
        elif icon_type == "pause":
            # ⏸ 暫停雙豎線 (實心)
            painter.setBrush(brush)
            w = size * 0.12
            margin_x = size * 0.34
            margin_y = size * 0.28
            painter.drawRect(QRectF(margin_x, margin_y, w, size - 2*margin_y))
            painter.drawRect(QRectF(size - margin_x - w, margin_y, w, size - 2*margin_y))
            
        elif icon_type == "stop":
            # ⏹ 停止正方形 (實心)
            painter.setBrush(brush)
            margin = size * 0.32
            painter.drawRect(QRectF(margin, margin, size - 2*margin, size - 2*margin))
            
        elif icon_type == "prev":
            # ⏮ 上一首 (左三角形 + 左豎線)
            painter.setBrush(brush)
            # 三角形
            path = QPainterPath()
            margin_x = size * 0.32
            margin_y = size * 0.28
            path.moveTo(size - margin_x, margin_y)
            path.lineTo(margin_x + 3, size / 2)
            path.lineTo(size - margin_x, size - margin_y)
            path.closeSubpath()
            painter.drawPath(path)
            # 左邊的豎線
            painter.drawLine(int(margin_x), int(margin_y), int(margin_x), int(size - margin_y))
            
        elif icon_type == "next":
            # ⏭ 下一首 (右三角形 + 右豎線)
            painter.setBrush(brush)
            # 三角形
            path = QPainterPath()
            margin_x = size * 0.32
            margin_y = size * 0.28
            path.moveTo(margin_x, margin_y)
            path.lineTo(size - margin_x - 3, size / 2)
            path.lineTo(margin_x, size - margin_y)
            path.closeSubpath()
            painter.drawPath(path)
            # 右邊的豎線
            painter.drawLine(int(size - margin_x), int(margin_y), int(size - margin_x), int(size - margin_y))
            
        elif icon_type == "refresh":
            # 🔄 重新整理 (圓弧箭頭)
            painter.setBrush(Qt.NoBrush)
            r = size * 0.26
            rect = QRectF(size/2 - r, size/2 - r, 2*r, 2*r)
            # 繪製一段 270 度的弧線 (從 45 度到 315 度)
            painter.drawArc(rect, 45 * 16, 270 * 16)
            
            # 在終點處繪製小箭頭
            angle = 45 * (math.pi / 180)
            ax = size/2 + r * math.cos(angle)
            ay = size/2 - r * math.sin(angle)
            
            painter.setBrush(brush)
            apath = QPainterPath()
            apath.moveTo(ax, ay)
            apath.lineTo(ax - 5, ay)
            apath.lineTo(ax, ay + 5)
            apath.closeSubpath()
            painter.drawPath(apath)
            
        elif icon_type == "network":
            # 🌐 網路 (三個相連的圓點)
            painter.setBrush(brush)
            # 頂點
            painter.drawEllipse(QRectF(size/2 - 3, size * 0.22, 6, 6))
            # 左下點
            painter.drawEllipse(QRectF(size * 0.22, size * 0.68, 6, 6))
            # 右下點
            painter.drawEllipse(QRectF(size * 0.68, size * 0.68, 6, 6))
            
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(int(size/2), int(size * 0.22 + 6), int(size * 0.22 + 3), int(size * 0.68))
            painter.drawLine(int(size/2), int(size * 0.22 + 6), int(size * 0.68 + 3), int(size * 0.68))
            painter.drawLine(int(size * 0.22 + 6), int(size * 0.68 + 3), int(size * 0.68), int(size * 0.68 + 3))

        elif icon_type == "chevron-up":
            # 展開/收起 向上箭頭 (V型)
            margin = size * 0.3
            painter.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(margin, size - margin)
            path.lineTo(size/2, margin + 2)
            path.lineTo(size - margin, size - margin)
            painter.drawPath(path)

        elif icon_type == "chevron-down":
            # 展開/收起 向下箭頭 (V型)
            margin = size * 0.3
            painter.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(margin, margin + 2)
            path.lineTo(size/2, size - margin)
            path.lineTo(size - margin, margin + 2)
            painter.drawPath(path)
            
        painter.end()
        
        # 關鍵點：為 QPixmap 設置物理與邏輯像素的比率，讓高畫質細節在 High DPI 螢幕上正確平滑渲染，徹底解決模糊問題。
        pixmap.setDevicePixelRatio(scale)
        return QIcon(pixmap)

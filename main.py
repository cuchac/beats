import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QWidget, QInputDialog
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize, QSettings, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QAction, QIcon, QPixmap, QFont
from pynput import keyboard

# Vynucení XCB (X11) platformy na Waylandu, aby fungovaly flagy jako "vždy navrchu"
if os.environ.get("XDG_SESSION_TYPE") == "wayland":
    os.environ["QT_QPA_PLATFORM"] = "xcb"

class HotkeySignaler(QObject):
    next_song = pyqtSignal()
    prev_song = pyqtSignal()

class RedDot(QWidget):
    def __init__(self):
        super().__init__()
        # Nastavení okna: bez rámečku, průhledné pozadí, vždy navrchu, nemožnost zaměření
        # Přidán flag ToolTip, který je na některých WM/Wayland více "agresivní" v bytí navrchu
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.ToolTip |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Velikost a pozice (pravý horní roh)
        self.dot_size = 60
        self.setFixedSize(self.dot_size, self.dot_size)
        
        # Načtení geometrie obrazovky
        screen = QApplication.primaryScreen().geometry()
        # Posun o 10px od okraje
        self.move(screen.width() - self.dot_size - 10, 10)
        
        self.is_active = False
        self.color = QColor(255, 0, 0)
        self.display_text = ""
        self.show()

    def set_active(self, active, color=None, text=""):
        self.is_active = active
        if color:
            self.color = color
        self.display_text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Pokud není aktivní, vyčistíme oblast (vytvoříme průhlednost)
        if not self.is_active:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
            return

        painter.setBrush(self.color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.dot_size, self.dot_size)
        
        if self.display_text:
            painter.setPen(Qt.GlobalColor.black)
            font = QFont("Arial", 20, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.display_text)

class BeatApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Beats")
        self.app.setOrganizationName("BeatsOrg")
        self.app.setQuitOnLastWindowClosed(False)
        
        self.settings = QSettings()
        self.load_settings()
        
        self.dot = RedDot()
        self.duration_ms = 300
        self.current_duration = self.duration_ms
        self.beat_count = 0  # Počítadlo úderů (0-3)
        
        # Časovač pro samotné údery (rytmus)
        self.beat_timer = QTimer()
        self.beat_timer.timeout.connect(self.start_beat)
        
        # Časovač pro skrytí tečky po 300ms
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(lambda: self.dot.set_active(False))
        
        self.setup_tray()
        # Inicializace info_action textu podle načtených nastavení
        self.update_tray_info()
        
        self.update_timers()
        self.setup_hotkeys()
        self.beat_timer.start()

    def setup_hotkeys(self):
        # Pomocný objekt pro přenos signálů z pynput vlákna do GUI vlákna
        self.hotkey_signaler = HotkeySignaler()
        self.hotkey_signaler.next_song.connect(self.next_song)
        self.hotkey_signaler.prev_song.connect(self.previous_song)

        # Globální klávesové zkratky pomocí pynput (běží v samostatném vlákně)
        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+<alt>+<left>': self.hotkey_signaler.prev_song.emit,
            '<ctrl>+<alt>+<right>': self.hotkey_signaler.next_song.emit
        })
        self.hotkey_listener.start()

    def load_settings(self):
        self.bpm = self.settings.value("bpm", 60, type=int)
        self.bpm_presets = self.settings.value("bpm_presets", [60, 80, 100, 120, 140, 160, 180, 200], type=list)
        # Převod na int, pokud by se načetly jako stringy
        self.bpm_presets = [int(v) for v in self.bpm_presets]
        self.current_preset_index = self.settings.value("current_preset_index", -1, type=int)

    def save_settings(self):
        self.settings.setValue("bpm", self.bpm)
        self.settings.setValue("bpm_presets", self.bpm_presets)
        self.settings.setValue("current_preset_index", self.current_preset_index)

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self.app)
        
        self.menu = QMenu()
        
        # Aktuální BPM info
        self.info_action = QAction(f"BPM: {self.bpm}", self.menu)
        self.info_action.setEnabled(False)
        self.menu.addAction(self.info_action)
        
        self.menu.addSeparator()

        # Vstup pro vlastní BPM
        custom_bpm_action = QAction("Zadat vlastní BPM...", self.menu)
        custom_bpm_action.triggered.connect(self.prompt_custom_bpm)
        self.menu.addAction(custom_bpm_action)
        
        self.menu.addSeparator()
        
        # Předdefinované BPM hodnoty
        self.rebuild_presets_menu()
        
        self.menu.addSeparator()

        # Možnost změnit předvolby
        config_presets_action = QAction("Nastavit předvolby BPM...", self.menu)
        config_presets_action.triggered.connect(self.prompt_config_presets)
        self.menu.addAction(config_presets_action)

        self.menu.addSeparator()
        
        quit_action = QAction("Ukončit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self.handle_tray_activation)
        self.tray_icon.show()

    def set_bpm(self, val, preset_index=-1, show_number=False):
        if val > 0:
            self.bpm = val
            self.current_preset_index = preset_index
            self.beat_count = 0  # Resetovat takt při změně BPM
            
            if show_number and preset_index >= 0:
                self.show_song_number(preset_index + 1)
                
            self.update_tray_info()
            self.update_timers()
            self.save_settings()
            self.rebuild_presets_menu()

    def show_song_number(self, number):
        # Zobrazí číslo skladby v tečce na 1 sekundu (nebo do příštího překreslení beatem)
        self.dot.set_active(True, QColor(255, 255, 255), str(number))
        self.hide_timer.start(1000)

    def update_tray_info(self):
        # Generování ikony s číslem skladby nebo BPM
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Pozadí (červený kruh)
        painter.setBrush(QColor(255, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 60, 60)
        
        # Text (číslo nebo BPM)
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        
        if self.current_preset_index >= 0 and self.current_preset_index < len(self.bpm_presets):
            song_num = str(self.current_preset_index + 1)
            info_text = f"Skladba {song_num}: {self.bpm} BPM"
            self.info_action.setText(info_text)
            self.tray_icon.setToolTip(f"Beats - Skladba {song_num}")
            
            # Vykreslení čísla skladby do ikony
            font.setPointSize(32 if len(song_num) < 2 else 24)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, song_num)
        else:
            self.info_action.setText(f"BPM: {self.bpm}")
            self.tray_icon.setToolTip(f"Beats - {self.bpm} BPM")
            
            # Vykreslení BPM nebo otazníku, pokud není preset
            font.setPointSize(20)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, str(self.bpm))
            
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))

    def handle_tray_activation(self, reason):
        # Trigger odpovídá kliknutí levým tlačítkem (v PyQt6)
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.next_song()

    def next_song(self):
        if not self.bpm_presets:
            return
            
        next_idx = (self.current_preset_index + 1) % len(self.bpm_presets)
        self.set_bpm(self.bpm_presets[next_idx], next_idx, show_number=True)

    def previous_song(self):
        if not self.bpm_presets:
            return
            
        prev_idx = (self.current_preset_index - 1) % len(self.bpm_presets)
        self.set_bpm(self.bpm_presets[prev_idx], prev_idx, show_number=True)

    def prompt_custom_bpm(self):
        val, ok = QInputDialog.getInt(None, "Nastavení BPM", "Zadejte BPM:", self.bpm, 1, 500)
        if ok:
            self.set_bpm(val)

    def prompt_config_presets(self):
        presets_str = ", ".join(map(str, self.bpm_presets))
        new_presets_str, ok = QInputDialog.getText(
            None, "Nastavení předvoleb", 
            "Zadejte hodnoty BPM oddělené čárkou (pořadí bude zachováno):", 
            text=presets_str
        )
        if ok:
            try:
                new_presets = [int(x.strip()) for x in new_presets_str.split(",") if x.strip().isdigit()]
                if new_presets:
                    self.bpm_presets = new_presets
                    self.current_preset_index = -1
                    self.save_settings()
                    self.rebuild_presets_menu()
            except ValueError:
                pass

    def rebuild_presets_menu(self):
        if hasattr(self, 'presets_menu'):
            self.presets_menu.clear()
        else:
            self.presets_menu = QMenu("Seznam skladeb (BPM)", self.menu)
            self.menu.addMenu(self.presets_menu)

        for i, val in enumerate(self.bpm_presets):
            prefix = "[AKTIVNÍ] " if i == self.current_preset_index else ""
            action = QAction(f"{prefix}{i+1}. skladba: {val} BPM", self.presets_menu)
            action.triggered.connect(lambda checked, v=val, idx=i: self.set_bpm(v, idx, show_number=True))
            if i == self.current_preset_index:
                font = action.font()
                font.setBold(True)
                action.setFont(font)
            self.presets_menu.addAction(action)

    def update_timers(self):
        # Interval v ms: (60 sekund / BPM) * 1000
        interval = int((60 / self.bpm) * 1000)
        self.beat_timer.setInterval(interval)
        # Pokud je interval kratší než trvání tečky, zkrátíme trvání tečky
        self.current_duration = min(self.duration_ms, interval - 50 if interval > 50 else 1)

    def start_beat(self):
        # 1. doba je červená, ostatní 3 jsou zelené
        if self.beat_count == 0:
            color = QColor(255, 0, 0)  # Červená
        else:
            color = QColor(0, 255, 0)  # Zelená
            
        self.dot.set_active(True, color)
        self.hide_timer.start(self.current_duration)
        
        # Zvýšit počítadlo (0, 1, 2, 3)
        self.beat_count = (self.beat_count + 1) % 4

    def run(self):
        sys.exit(self.app.exec())

def main():
    app = BeatApp()
    app.run()

if __name__ == "__main__":
    main()

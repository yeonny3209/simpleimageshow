#!/usr/bin/env python3
"""simpleimageshow - 사진 하나를 다른 프로그램 화면 위에 항상 떠 있게 보여주는 프로그램.

사용법:
    python simpleimageshow.py [이미지 경로]

경로를 주지 않으면 파일 선택 창이 열린다.

조작:
    왼쪽 드래그         창 이동
    마우스 휠           확대 / 축소
    Ctrl + 마우스 휠    투명도 조절
    오른쪽 클릭         메뉴
    + / -              확대 / 축소
    0                  원래 크기
    [ / ]              투명도 낮추기 / 높이기
    O                  다른 사진 열기
    T                  항상 위 켜기 / 끄기
    L                  위치 잠금 켜기 / 끄기
    Esc / Q            종료
"""

import sys
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from PIL import Image, ImageTk
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "simpleimageshow",
        "Pillow 라이브러리가 필요합니다.\n\n  pip install pillow\n\n를 실행한 뒤 다시 시도하세요.",
    )
    sys.exit(1)

FILE_TYPES = [
    ("이미지", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff *.ico"),
    ("모든 파일", "*.*"),
]
MIN_SCALE = 0.05
MAX_SCALE = 10.0
ZOOM_STEP = 1.1
MIN_ALPHA = 0.1
ALPHA_STEP = 0.05


class ImageOverlay:
    def __init__(self, root, path):
        self.root = root
        self.original = None
        self.photo = None
        self.scale = 1.0
        self.alpha = 1.0
        self.topmost = tk.BooleanVar(value=True)
        self.locked = tk.BooleanVar(value=False)
        self._drag_offset = None
        self.ok = False

        root.overrideredirect(True)  # 테두리/제목 표시줄 없음
        root.attributes("-topmost", True)
        root.configure(bg="black")

        self.label = tk.Label(root, bd=0, highlightthickness=0, bg="black")
        self.label.pack()

        self._build_menu()
        self._bind_events()

        if not self.load(path):
            root.destroy()
            return

        # 처음에는 화면 가운데에 띄운다
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.ok = True

    # ---------- 이미지 ----------

    def load(self, path):
        try:
            img = Image.open(path)
            img.load()
        except Exception as e:  # 손상된 파일, 지원하지 않는 형식 등
            messagebox.showerror("simpleimageshow", f"사진을 열 수 없습니다.\n\n{path}\n\n{e}")
            return False

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        self.original = img

        # 화면보다 크면 화면의 80% 안에 들어가도록 줄인다
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        fit = min(sw * 0.8 / img.width, sh * 0.8 / img.height, 1.0)
        self.scale = max(fit, MIN_SCALE)
        self.root.title(f"simpleimageshow - {path}")
        self.render()
        return True

    def render(self):
        w = max(1, round(self.original.width * self.scale))
        h = max(1, round(self.original.height * self.scale))
        resized = self.original.resize((w, h), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(resized)
        self.label.configure(image=self.photo)
        self.root.geometry(f"{w}x{h}")

    def zoom(self, factor, anchor=None):
        new_scale = min(max(self.scale * factor, MIN_SCALE), MAX_SCALE)
        if new_scale == self.scale:
            return
        # anchor(화면 좌표)가 가리키는 사진 위의 점이 제자리에 머물도록 창 위치를 보정
        x0, y0 = self.root.winfo_x(), self.root.winfo_y()
        if anchor is None:
            anchor = (x0 + self.root.winfo_width() // 2, y0 + self.root.winfo_height() // 2)
        ax, ay = anchor
        ratio = new_scale / self.scale
        nx = round(ax - (ax - x0) * ratio)
        ny = round(ay - (ay - y0) * ratio)
        self.scale = new_scale
        self.render()
        self.root.geometry(f"+{nx}+{ny}")

    def reset_zoom(self):
        self.zoom(1.0 / self.scale)

    def set_alpha(self, value):
        self.alpha = min(max(value, MIN_ALPHA), 1.0)
        self.root.attributes("-alpha", self.alpha)

    def open_other(self):
        path = filedialog.askopenfilename(parent=self.root, title="사진 열기", filetypes=FILE_TYPES)
        if path:
            self.load(path)

    # ---------- 이벤트 ----------

    def _build_menu(self):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="다른 사진 열기 (O)", command=self.open_other)
        m.add_separator()
        m.add_command(label="확대 (+)", command=lambda: self.zoom(ZOOM_STEP))
        m.add_command(label="축소 (-)", command=lambda: self.zoom(1 / ZOOM_STEP))
        m.add_command(label="원래 크기 (0)", command=self.reset_zoom)
        m.add_separator()
        alpha_menu = tk.Menu(m, tearoff=0)
        for pct in (100, 80, 60, 40, 20):
            alpha_menu.add_command(label=f"{pct}%", command=lambda p=pct: self.set_alpha(p / 100))
        m.add_cascade(label="투명도", menu=alpha_menu)
        m.add_checkbutton(label="항상 위 (T)", variable=self.topmost, command=self._apply_topmost)
        m.add_checkbutton(label="위치 잠금 (L)", variable=self.locked)
        m.add_separator()
        m.add_command(label="종료 (Esc)", command=self.root.destroy)
        self.menu = m

    def _bind_events(self):
        r = self.root
        self.label.bind("<ButtonPress-1>", self._drag_start)
        self.label.bind("<B1-Motion>", self._drag_move)
        self.label.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag_offset", None))
        self.label.bind("<Button-3>", self._show_menu)
        if sys.platform == "darwin":  # macOS 는 Button-2 가 오른쪽 클릭
            self.label.bind("<Button-2>", self._show_menu)

        # 휠: Windows/macOS 는 <MouseWheel>, X11(Linux) 은 Button-4/5
        r.bind("<MouseWheel>", lambda e: self._wheel(e, 1 if e.delta > 0 else -1))
        r.bind("<Button-4>", lambda e: self._wheel(e, 1))
        r.bind("<Button-5>", lambda e: self._wheel(e, -1))

        r.bind("<Escape>", lambda e: r.destroy())
        r.bind("<KeyPress-q>", lambda e: r.destroy())
        r.bind("<KeyPress-plus>", lambda e: self.zoom(ZOOM_STEP))
        r.bind("<KeyPress-equal>", lambda e: self.zoom(ZOOM_STEP))
        r.bind("<KeyPress-KP_Add>", lambda e: self.zoom(ZOOM_STEP))
        r.bind("<KeyPress-minus>", lambda e: self.zoom(1 / ZOOM_STEP))
        r.bind("<KeyPress-KP_Subtract>", lambda e: self.zoom(1 / ZOOM_STEP))
        r.bind("<KeyPress-0>", lambda e: self.reset_zoom())
        r.bind("<KeyPress-bracketleft>", lambda e: self.set_alpha(self.alpha - ALPHA_STEP))
        r.bind("<KeyPress-bracketright>", lambda e: self.set_alpha(self.alpha + ALPHA_STEP))
        r.bind("<KeyPress-o>", lambda e: self.open_other())
        r.bind("<KeyPress-t>", lambda e: self._toggle(self.topmost, self._apply_topmost))
        r.bind("<KeyPress-l>", lambda e: self._toggle(self.locked))

    def _drag_start(self, e):
        self.root.focus_force()  # 테두리 없는 창은 클릭해야 키 입력을 받는다
        if self.locked.get():
            self._drag_offset = None
            return
        self._drag_offset = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _drag_move(self, e):
        if self._drag_offset is None:
            return
        dx, dy = self._drag_offset
        self.root.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    def _wheel(self, e, direction):
        if e.state & 0x0004:  # Ctrl
            self.set_alpha(self.alpha + direction * ALPHA_STEP)
        else:
            self.zoom(ZOOM_STEP if direction > 0 else 1 / ZOOM_STEP, (e.x_root, e.y_root))

    def _show_menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _toggle(self, var, callback=None):
        var.set(not var.get())
        if callback:
            callback()

    def _apply_topmost(self):
        self.root.attributes("-topmost", self.topmost.get())


def main():
    root = tk.Tk()
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        root.withdraw()
        path = filedialog.askopenfilename(title="띄울 사진 선택", filetypes=FILE_TYPES)
        if not path:
            return
        root.deiconify()
    if ImageOverlay(root, path).ok:
        root.mainloop()


if __name__ == "__main__":
    main()

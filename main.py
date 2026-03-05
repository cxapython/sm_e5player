# -*- coding: utf-8 -*-
"""
SM Arrow Player - 主程序入口
整合所有模块，实现歌曲浏览和播放功能
"""

import os
import sys
import traceback

# 检查依赖
try:
    import customtkinter as ctk
    CTk_AVAILABLE = True
except ImportError:
    CTk_AVAILABLE = False
    print("错误: 缺少 customtkinter 库，请运行: pip install customtkinter")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("警告: 缺少 pygame 库，部分功能受限，请运行: pip install pygame")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: 缺少 Pillow 库，封面显示受限，请运行: pip install Pillow")

# 导入自定义模块
from config_manager import ConfigManager
from directory_parser import DirectoryParser, SongInfo
from song_scanner import SongScanner
from audio_player import AudioPreviewPlayer
from ui_components import SongBrowser

import tkinter.filedialog as fd
import tkinter.messagebox as messagebox


class SMPlayerApp:
    """SM Arrow Player 主应用程序"""

    def __init__(self):
        """初始化应用程序"""
        # 检查依赖
        if not CTk_AVAILABLE:
            print("无法启动：缺少必要的依赖库 customtkinter")
            sys.exit(1)

        # 设置外观
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 初始化模块
        self.config = ConfigManager()
        self.scanner = SongScanner()
        self.audio_player = AudioPreviewPlayer()

        # 主窗口
        self.root = ctk.CTk()
        self.root.title("SM Arrow Player")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # 浏览器组件
        self.browser = None

        # 播放器窗口引用
        self._player_window = None

    def run(self):
        """运行应用程序"""
        # 检查是否首次运行
        if self.config.is_first_run():
            self._show_path_selector()
        else:
            self._load_and_show_main()

        # 运行主循环
        self.root.mainloop()

    def _show_path_selector(self):
        """显示路径选择对话框（首次运行）"""
        # 清空窗口
        for widget in self.root.winfo_children():
            widget.destroy()

        dialog_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        dialog_frame.pack(fill="both", expand=True, padx=30, pady=30)

        # 标题
        title = ctk.CTkLabel(
            dialog_frame,
            text="欢迎使用 SM Arrow Player",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=("#4ECDC4", "#4ECDC4")
        )
        title.pack(pady=(0, 10))

        # 说明
        desc = ctk.CTkLabel(
            dialog_frame,
            text="首次运行，请选择包含歌曲文件的目录\n（每个子目录应包含 .sm 谱面文件）",
            font=ctk.CTkFont(size=14),
            text_color=("gray70", "gray50"),
            justify="center"
        )
        desc.pack(pady=(0, 25))

        # 路径输入
        path_var = ctk.StringVar(value=self._detect_songs_path())

        path_entry = ctk.CTkEntry(
            dialog_frame,
            textvariable=path_var,
            placeholder_text="选择或输入歌曲目录路径...",
            height=40,
            font=ctk.CTkFont(size=13),
            corner_radius=10
        )
        path_entry.pack(fill="x", pady=(0, 15))

        # 按钮行
        btn_frame = ctk.CTkFrame(dialog_frame, fg_color="transparent")
        btn_frame.pack(pady=(0, 20))

        def browse():
            path = fd.askdirectory(
                title="选择歌曲目录",
                initialdir=path_var.get() or os.path.expanduser("~")
            )
            if path:
                path_var.set(path)

        browse_btn = ctk.CTkButton(
            btn_frame,
            text="浏览...",
            width=100,
            height=36,
            font=ctk.CTkFont(size=13),
            corner_radius=10,
            command=browse
        )
        browse_btn.pack(side="left", padx=5)

        # 状态标签
        status_label = ctk.CTkLabel(
            dialog_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("#FF6B6B", "#FF6B6B")
        )
        status_label.pack(pady=(0, 15))

        def on_confirm():
            path = path_var.get().strip()
            if not path:
                status_label.configure(text="请选择歌曲目录")
                return
            if not os.path.isdir(path):
                status_label.configure(text="目录不存在，请重新选择")
                return

            # 检查是否有歌曲
            test_scanner = SongScanner(path)
            songs = test_scanner.scan()
            if not songs:
                status_label.configure(text="目录中没有找到歌曲文件")
                return

            # 保存配置
            self.config.set_scan_path(path)
            self.config.save()
            self._load_and_show_main()

        confirm_btn = ctk.CTkButton(
            btn_frame,
            text="确认",
            width=120,
            height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=10,
            command=on_confirm
        )
        confirm_btn.pack(side="left", padx=5)

        # 提示
        tip = ctk.CTkLabel(
            dialog_frame,
            text="提示：目录路径将保存到配置文件，下次启动自动加载",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray30")
        )
        tip.pack(pady=(10, 0))

    def _detect_songs_path(self) -> str:
        """尝试自动检测 songs 目录"""
        # 检查程序所在目录
        app_dir = os.path.dirname(os.path.abspath(__file__))
        songs_path = os.path.join(app_dir, "songs")
        if os.path.isdir(songs_path):
            return songs_path

        # 检查上级目录
        parent_dir = os.path.dirname(app_dir)
        songs_path = os.path.join(parent_dir, "songs")
        if os.path.isdir(songs_path):
            return songs_path

        return ""

    def _load_and_show_main(self):
        """加载并显示主界面"""
        scan_path = self.config.get_scan_path()

        # 扫描歌曲
        if scan_path:
            self.scanner.scan_path = scan_path

            # 显示加载界面
            self._show_loading()

            # 执行扫描
            self.scanner.scan()

        # 显示主界面
        self._show_main_ui()

    def _show_loading(self):
        """显示加载界面"""
        for widget in self.root.winfo_children():
            widget.destroy()

        loading_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        loading_frame.pack(fill="both", expand=True)

        loading_label = ctk.CTkLabel(
            loading_frame,
            text="正在扫描歌曲...",
            font=ctk.CTkFont(size=20),
            text_color=("#4ECDC4", "#4ECDC4")
        )
        loading_label.pack(expand=True)

        # 强制更新UI
        self.root.update()

    def _show_main_ui(self):
        """显示主界面"""
        # 清空窗口
        for widget in self.root.winfo_children():
            widget.destroy()

        # 创建浏览器
        self.browser = SongBrowser(
            self.root,
            on_song_select=self._on_song_select
        )
        self.browser.pack(fill="both", expand=True)

        # 设置回调
        self.browser.set_audio_callbacks(
            on_preview=self._on_song_preview,
            on_stop=self._on_preview_stop
        )
        self.browser.set_refresh_callback(self._on_refresh)
        self.browser.set_settings_callback(self._on_settings)

        # 显示歌曲
        self.browser.set_songs(self.scanner.songs)

        # 恢复上次页码
        last_page = self.config.get_last_page()
        if last_page > 0:
            self.browser.go_to_page(last_page)

        # 窗口关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_song_select(self, song: SongInfo):
        """歌曲选择事件"""
        if not song.has_sm:
            return

        # 停止预览
        self.audio_player.stop()

        # 保存上次播放
        self.config.set_last_sm_file(song.sm_file)
        self.config.set_last_page(self.browser.current_page)
        self.config.save()

        # 隐藏主窗口
        self.root.withdraw()

        # 启动播放器
        try:
            self._launch_player(song)
        except Exception as e:
            messagebox.showerror("错误", f"启动播放器失败：{str(e)}")
            self.root.deiconify()

    def _on_song_preview(self, song: SongInfo):
        """歌曲预览事件"""
        if song.has_audio:
            self.audio_player.preview(song.audio_file)

    def _on_preview_stop(self):
        """停止预览"""
        self.audio_player.stop()

    def _on_refresh(self):
        """刷新歌曲列表"""
        # 停止预览
        self.audio_player.stop()

        # 重新扫描
        self.scanner.refresh()

        # 更新浏览器
        self.browser.set_songs(self.scanner.songs)

    def _on_settings(self):
        """设置按钮"""
        # 显示路径选择对话框
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("设置")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 400) // 2
        y = (dialog.winfo_screenheight() - 200) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        # 标题
        title = ctk.CTkLabel(
            frame,
            text="设置歌曲目录",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(pady=(0, 15))

        # 当前路径
        current_path = self.config.get_scan_path()
        path_var = ctk.StringVar(value=current_path)

        path_entry = ctk.CTkEntry(
            frame,
            textvariable=path_var,
            height=36,
            font=ctk.CTkFont(size=13)
        )
        path_entry.pack(fill="x", pady=(0, 10))

        def browse():
            path = fd.askdirectory(
                title="选择歌曲目录",
                initialdir=path_var.get()
            )
            if path:
                path_var.set(path)

        browse_btn = ctk.CTkButton(
            frame,
            text="浏览...",
            width=80,
            command=browse
        )
        browse_btn.pack(pady=(0, 15))

        def save():
            new_path = path_var.get().strip()
            if new_path and os.path.isdir(new_path):
                self.config.set_scan_path(new_path)
                self.config.save()
                self.scanner.scan_path = new_path
                self._on_refresh()
                dialog.destroy()
            else:
                messagebox.showwarning("提示", "请选择有效的目录")

        save_btn = ctk.CTkButton(
            frame,
            text="保存",
            width=100,
            command=save
        )
        save_btn.pack()

    def _launch_player(self, song: SongInfo):
        """启动播放器"""
        # 导入播放器模块
        from sm_arrow_player import ArrowPlayer

        # 获取皮肤目录
        app_dir = os.path.dirname(os.path.abspath(__file__))
        skin_dir = os.path.join(app_dir, "noteskin")

        if not os.path.isdir(skin_dir):
            raise FileNotFoundError(f"皮肤目录不存在：{skin_dir}")

        # 创建播放器
        sm_path = song.sm_file
        audio_path = song.audio_file

        player = ArrowPlayer(sm_path, audio_path, skin_dir)
        player.load_sm()
        player.init_pygame()
        player.play()

        # 运行播放器
        end_reason = player.main_loop()

        # 播放结束，恢复主窗口
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_close(self):
        """窗口关闭处理"""
        # 停止音频
        self.audio_player.cleanup()

        # 保存配置
        if self.browser:
            self.config.set_last_page(self.browser.current_page)
        self.config.save()

        # 关闭窗口
        self.root.destroy()


def main():
    """程序入口"""
    app = SMPlayerApp()
    app.run()


if __name__ == "__main__":
    main()

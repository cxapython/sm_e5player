# -*- coding: utf-8 -*-
"""
macOS ScreenCaptureKit 录屏器
使用原生 ScreenCaptureKit 框架进行高性能窗口捕获和录制
"""

import os
import time
import subprocess
import threading
from typing import Tuple, Optional, List, Dict
from datetime import datetime
from dataclasses import dataclass

# 检查是否在 macOS 上
import platform
IS_MACOS = platform.system() == 'Darwin'

if IS_MACOS:
    try:
        from AppKit import NSApp, NSObject, NSArray, NSString, NSImage
        from AVFoundation import (
            AVAssetWriter, AVAssetWriterInput,
            AVAssetWriterInputPixelBufferAdaptor,
            CMTimeMake, CMTimeGetSeconds, CVPixelBufferRetain
        )
        from CoreMedia import CMSampleBufferGetImageBuffer, CMSampleBufferGetPresentationTimeStamp
        from Quartz import (
            CGWindowListCopyWindowInfo, kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly, kCVPixelFormatType_32BGRA,
            CFURLCreateWithFileSystemPath, kCFURLPOSIXPathStyle,
            CGWindowListCreateImage, kCGWindowImageBoundsIgnoreFraming,
            kCGWindowImageNominalResolution, kCGWindowIDCFNumberNumberType
        )
        import Quartz
        SCREEN_CAPTURE_AVAILABLE = True
    except ImportError as e:
        SCREEN_CAPTURE_AVAILABLE = False
        print(f"[ScreenRecorder] pyobjc 未安装: {e}")
        print("[ScreenRecorder] 请运行: pip install pyobjc-core pyobjc-framework-Quartz pyobjc-framework-AVFoundation")
else:
    SCREEN_CAPTURE_AVAILABLE = False


@dataclass
class WindowInfo:
    """窗口信息"""
    window_id: int
    title: str
    owner_name: str  # 应用名称
    owner_pid: int
    x: int
    y: int
    width: int
    height: int
    thumbnail: Optional['QPixmap'] = None  # 窗口缩略图


def get_window_list(include_minimized: bool = False) -> List[WindowInfo]:
    """获取所有可见窗口列表

    Args:
        include_minimized: 是否包含最小化的窗口

    Returns:
        窗口信息列表
    """
    if not IS_MACOS:
        return []

    try:
        from Quartz import (
            CGWindowListCopyWindowInfo, kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly
        )

        if include_minimized:
            options = kCGNullWindowID
        else:
            options = kCGWindowListOptionOnScreenOnly

        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)

        windows = []
        for window_info in window_list:
            window_id = window_info.get('kCGWindowNumber', 0)
            owner_name = window_info.get('kCGWindowOwnerName', '')
            owner_pid = window_info.get('kCGWindowOwnerPID', 0)
            window_name = window_info.get('kCGWindowName', '')
            bounds = window_info.get('kCGWindowBounds', {})

            # 安全解析边界值
            try:
                x = int(bounds.get('X', 0) or 0)
                y = int(bounds.get('Y', 0) or 0)
                w = int(bounds.get('Width', 0) or 0)
                h = int(bounds.get('Height', 0) or 0)
            except (ValueError, OverflowError):
                continue

            # 过滤无效窗口
            if w < 100 or h < 100:
                continue

            # 过滤没有名称的窗口（通常是系统窗口）
            if not window_name and not owner_name:
                continue

            # 过滤系统窗口
            if owner_name in ('Window Server', 'Dock', 'MenuBar', 'WindowManager', '墙纸'):
                continue

            # 过滤明显的系统窗口名称
            system_keywords = ['Shield Window', 'Overlay', 'Offscreen', 'Shadow']
            if any(kw in window_name for kw in system_keywords):
                continue

            # 标题优先使用窗口名称，否则使用应用名称
            title = window_name if window_name else owner_name

            windows.append(WindowInfo(
                window_id=window_id,
                title=title,
                owner_name=owner_name,
                owner_pid=owner_pid,
                x=x,
                y=y,
                width=w,
                height=h
            ))

        # 按应用名和标题排序
        windows.sort(key=lambda w: (w.owner_name.lower(), w.title.lower()))

        return windows

    except Exception as e:
        print(f"[ScreenRecorder] 获取窗口列表失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_window_thumbnail(window_id: int, max_size: int = 200) -> Optional['QPixmap']:
    """获取窗口缩略图

    Args:
        window_id: 窗口 ID
        max_size: 最大尺寸

    Returns:
        QPixmap 或 None
    """
    if not IS_MACOS:
        return None

    try:
        from PyQt6.QtGui import QPixmap, QImage
        from PyQt6.QtCore import Qt
        from Quartz import (
            CGWindowListCreateImage, kCGNullWindowID,
            kCGWindowImageBoundsIgnoreFraming,
            kCGWindowImageNominalResolution
        )
        import Quartz

        # 创建窗口截图
        window_id_number = Quartz.CFNumberCreate(None, kCGWindowIDCFNumberNumberType, window_id)
        window_array = Quartz.CFArrayCreate(None, [window_id_number], 1, None)

        image_ref = CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            window_id,
            kCGWindowImageBoundsIgnoreFraming | kCGWindowImageNominalResolution
        )

        if image_ref is None:
            return None

        # 获取图像尺寸
        width = Quartz.CGImageGetWidth(image_ref)
        height = Quartz.CGImageGetHeight(image_ref)

        if width == 0 or height == 0:
            return None

        # 计算缩放比例
        scale = min(max_size / width, max_size / height, 1.0)
        new_width = int(width * scale)
        new_height = int(height * scale)

        # 转换为 QPixmap
        # 使用 NSImage 作为中间格式
        from AppKit import NSImage, NSBitmapImageRep
        ns_image = NSImage.alloc().initWithCGImage_size_(image_ref, (width, height))

        # 转换为 PNG 数据
        tiff_data = ns_image.TIFFRepresentation()
        bitmap_rep = NSBitmapImageRep.imageRepWithData_(tiff_data)
        png_data = bitmap_rep.representationUsingType_properties_(
            Quartz.NSBitmapImageFileTypePNG, {}
        )

        # 创建 QPixmap
        pixmap = QPixmap()
        pixmap.loadFromData(bytes(png_data))

        if not pixmap.isNull():
            # 缩放
            return pixmap.scaled(
                new_width, new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

        return None

    except Exception as e:
        print(f"[ScreenRecorder] 获取窗口缩略图失败: {e}")
        return None


class WindowSelector:
    """窗口选择对话框（类似 OBS）"""

    def __init__(self, parent=None):
        self._parent = parent
        self._selected_window: Optional[WindowInfo] = None
        self._dialog = None

    def select_window(self, current_window_id: int = None) -> Optional[WindowInfo]:
        """显示窗口选择对话框

        Args:
            current_window_id: 当前窗口 ID（会被标记为默认选项）

        Returns:
            选中的窗口信息，或 None（取消选择）
        """
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QListWidget, QListWidgetItem, QPushButton, QWidget,
            QFrame, QScrollArea, QGridLayout
        )
        from PyQt6.QtCore import Qt, QSize
        from PyQt6.QtGui import QPixmap, QFont

        # 获取窗口列表
        windows = get_window_list()
        if not windows:
            return None

        # 创建对话框
        dialog = QDialog(self._parent)
        dialog.setWindowTitle("选择录制窗口")
        dialog.setMinimumSize(700, 500)
        dialog.resize(800, 600)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 提示文字
        hint_label = QLabel("请选择要录制的窗口：")
        hint_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(hint_label)

        # 窗口网格容器
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #444;
                border-radius: 8px;
                background: #1a1a1a;
            }
        """)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(10)
        grid.setContentsMargins(10, 10, 10, 10)

        # 存储窗口信息
        window_widgets = []
        self._selected_window = None

        def on_window_clicked(window_info: WindowInfo, item_widget: QWidget):
            # 清除之前的选中状态
            for w in window_widgets:
                w.setStyleSheet(w.styleSheet().replace("border: 3px solid #00a8ff;", "border: 2px solid #333;"))

            # 设置选中状态
            item_widget.setStyleSheet(item_widget.styleSheet().replace("border: 2px solid #333;", "border: 3px solid #00a8ff;"))
            self._selected_window = window_info

        # 添加窗口卡片
        col = 0
        row = 0
        max_cols = 3

        for i, window in enumerate(windows):
            # 创建窗口卡片
            card = QFrame()
            card.setFixedSize(220, 180)
            card.setStyleSheet("""
                QFrame {
                    background: #2a2a2a;
                    border: 2px solid #333;
                    border-radius: 8px;
                }
                QFrame:hover {
                    background: #333;
                    border-color: #555;
                }
            """)
            card.setCursor(Qt.CursorShape.PointingHandCursor)

            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(5)
            card_layout.setContentsMargins(8, 8, 8, 8)

            # 缩略图
            thumb_label = QLabel()
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_label.setFixedSize(200, 112)
            thumb_label.setStyleSheet("background: #1a1a1a; border-radius: 4px;")

            # 获取缩略图（异步）
            thumbnail = get_window_thumbnail(window.window_id, 200)
            if thumbnail and not thumbnail.isNull():
                thumb_label.setPixmap(thumbnail)
            else:
                thumb_label.setText("无预览")
                thumb_label.setStyleSheet("background: #1a1a1a; border-radius: 4px; color: #666;")

            card_layout.addWidget(thumb_label)

            # 应用名称
            owner_label = QLabel(window.owner_name[:25])
            owner_label.setStyleSheet("color: #888; font-size: 10px;")
            owner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(owner_label)

            # 窗口标题
            title_label = QLabel(window.title[:30])
            title_label.setStyleSheet("color: #fff; font-size: 11px; font-weight: bold;")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(title_label)

            # 尺寸信息
            size_label = QLabel(f"{window.width}x{window.height}")
            size_label.setStyleSheet("color: #555; font-size: 9px;")
            size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(size_label)

            # 如果是当前窗口，标记为默认
            if window.window_id == current_window_id:
                card.setStyleSheet(card.styleSheet().replace("border: 2px solid #333;", "border: 3px solid #00a8ff;"))
                self._selected_window = window

            # 点击事件
            card.mousePressEvent = lambda e, w=window, c=card: on_window_clicked(w, c)

            grid.addWidget(card, row, col)
            window_widgets.append(card)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #444;
                color: #fff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #555;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)

        ok_btn = QPushButton("确定")
        ok_btn.setFixedSize(100, 36)
        ok_btn.setStyleSheet("""
            QPushButton {
                background: #00a8ff;
                color: #fff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #0090e0;
            }
        """)
        ok_btn.clicked.connect(dialog.accept)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        # 显示对话框
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return self._selected_window

        return None


class ScreenRecorder:
    """macOS ScreenCaptureKit 录屏器 - 使用 SCStream 捕获窗口"""

    RESOLUTIONS = {
        "1080p": (1920, 1080),
        "720p": (1280, 720),
    }

    def __init__(self):
        self._stream = None
        self._writer = None
        self._video_input = None
        self._adaptor = None
        self._is_recording = False
        self._output_path = ""
        self._frame_count = 0
        self._start_time = 0.0
        self._lock = threading.Lock()
        self._audio_path = None
        self._resolution = "1080p"
        self._target_w = 1920
        self._target_h = 1080
        self._fps = 60
        self._cg_window_id = None
        self._delegate = None
        self._sample_handler = None
        self._stream_config = None
        self._content_filter = None

    def set_resolution(self, resolution: str):
        if resolution in self.RESOLUTIONS:
            self._resolution = resolution
            self._target_w, self._target_h = self.RESOLUTIONS[resolution]

    def get_resolution(self) -> str:
        return self._resolution

    def get_resolution_size(self) -> Tuple[int, int]:
        return self._target_w, self._target_h

    def is_recording(self) -> bool:
        return self._is_recording

    def get_recording_time(self) -> float:
        if not self._is_recording or self._start_time == 0:
            return 0.0
        return time.time() - self._start_time

    def _find_window_by_qt_id(self, qt_window_id: int) -> Optional[int]:
        """根据 Qt 窗口 ID 查找 macOS CGWindowID"""
        if not SCREEN_CAPTURE_AVAILABLE:
            return None

        try:
            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID
            )

            # 获取当前进程 ID
            current_pid = os.getpid()

            # 首先尝试精确匹配 Qt window ID
            for window_info in window_list:
                window_id = window_info.get('kCGWindowNumber', 0)
                if window_id == qt_window_id:
                    print(f"[ScreenRecorder] 精确匹配窗口 ID: {window_id}")
                    return window_id

            # 如果精确匹配失败，查找当前进程的可视窗口
            for window_info in window_list:
                owner_pid = window_info.get('kCGWindowOwnerPID', 0)
                if owner_pid == current_pid:
                    window_name = window_info.get('kCGWindowName', '')
                    window_id = window_info.get('kCGWindowNumber', 0)
                    # 跳过没有名称的窗口（通常是隐藏窗口）
                    if window_name and window_id > 0:
                        print(f"[ScreenRecorder] 找到进程窗口: {window_name} (ID: {window_id})")
                        return window_id

            # 如果还是没有找到，返回当前进程第一个有效窗口
            for window_info in window_list:
                owner_pid = window_info.get('kCGWindowOwnerPID', 0)
                if owner_pid == current_pid:
                    window_id = window_info.get('kCGWindowNumber', 0)
                    if window_id > 0:
                        print(f"[ScreenRecorder] 使用进程第一个窗口: {window_id}")
                        return window_id

            print("[ScreenRecorder] 未找到合适的窗口")
            return None

        except Exception as e:
            print(f"[ScreenRecorder] 查找窗口失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def start(self, qt_window_id: int, output_path: str, audio_path: str = None) -> bool:
        """开始录制指定窗口"""
        if not SCREEN_CAPTURE_AVAILABLE:
            print("[ScreenRecorder] ScreenCaptureKit 不可用，请安装 pyobjc")
            return False

        with self._lock:
            if self._is_recording:
                return False

            try:
                self._audio_path = audio_path
                self._output_path = output_path
                self._frame_count = 0

                # 查找窗口
                cg_window_id = self._find_window_by_qt_id(int(qt_window_id))
                if cg_window_id is None:
                    print("[ScreenRecorder] 未找到对应的窗口")
                    return False

                self._cg_window_id = cg_window_id

                # 创建输出目录
                output_dir = os.path.dirname(output_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)

                # 使用 ScreenCaptureKit (macOS 12.3+)
                # 通过 PyObjC 调用
                success = self._start_screencapturekit(output_path, cg_window_id)
                if not success:
                    print("[ScreenRecorder] ScreenCaptureKit 启动失败，尝试使用旧方案")
                    # 降级方案不可用，直接返回失败
                    return False

                self._is_recording = True
                self._start_time = time.time()
                print(f"[ScreenRecorder] 开始录制: {output_path}")
                return True

            except Exception as e:
                print(f"[ScreenRecorder] 启动失败: {e}")
                import traceback
                traceback.print_exc()
                self._cleanup()
                return False

    def _start_screencapturekit(self, output_path: str, window_id: int) -> bool:
        """使用 ScreenCaptureKit 录制"""
        try:
            # 动态加载 ScreenCaptureKit 框架
            from objc import loadBundleFramework
            import objc

            # 尝试加载 ScreenCaptureKit
            try:
                ScreenCaptureKit = objc.loadBundle(
                    "ScreenCaptureKit",
                    bundle_path="/System/Library/Frameworks/ScreenCaptureKit.framework",
                    module_globals=globals()
                )
            except:
                print("[ScreenRecorder] ScreenCaptureKit 框架加载失败（需要 macOS 12.3+）")
                return False

            # 获取 SCShareableContent
            SCScreenCaptureManager = objc.lookUpClass("SCScreenCaptureManager")
            SCShareableContent = objc.lookUpClass("SCShareableContent")

            # 这里需要异步获取窗口列表，简化处理
            # 实际实现需要使用 completionHandler

            print("[ScreenRecorder] ScreenCaptureKit 已加载")
            # 暂时返回 False，使用其他方案
            return False

        except Exception as e:
            print(f"[ScreenRecorder] ScreenCaptureKit 方案失败: {e}")
            return False

    def stop(self) -> Tuple[bool, str, int]:
        """停止录制"""
        with self._lock:
            if not self._is_recording:
                return False, "", 0

            self._is_recording = False

            try:
                # 停止流
                if self._stream:
                    try:
                        self._stream.stopCapture()
                    except:
                        pass

                # 结束写入
                if self._writer:
                    try:
                        if self._video_input:
                            self._video_input.markAsFinished()
                        self._writer.finishWriting()
                    except:
                        pass

            except Exception as e:
                print(f"[ScreenRecorder] 停止时出错: {e}")

            path = self._output_path
            frames = self._frame_count

            duration = frames / self._fps if frames > 0 else 0
            print(f"[ScreenRecorder] 完成: {path}, {frames}帧 ({duration:.1f}秒)")

            # 合并音频
            if self._audio_path and path and os.path.exists(path):
                merged = self._merge_audio(path, self._audio_path)
                if merged:
                    pass  # 已合并

            self._cleanup()

            return True, path, frames

    def _merge_audio(self, video_path: str, audio_path: str) -> bool:
        if not os.path.exists(audio_path):
            return False

        try:
            base, ext = os.path.splitext(video_path)
            merged_path = f"{base}_audio{ext}"

            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                merged_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=60)

            if result.returncode == 0 and os.path.exists(merged_path):
                os.remove(video_path)
                os.rename(merged_path, video_path)
                print(f"[ScreenRecorder] 音频合并完成")
                return True
            else:
                if os.path.exists(merged_path):
                    os.remove(merged_path)
                print(f"[ScreenRecorder] 音频合并失败")
                return False

        except Exception as e:
            print(f"[ScreenRecorder] 音频合并出错: {e}")
            return False

    def _cleanup(self):
        """清理资源"""
        self._stream = None
        self._writer = None
        self._video_input = None
        self._adaptor = None
        self._delegate = None
        self._sample_handler = None
        self._stream_config = None
        self._content_filter = None
        self._output_path = ""
        self._frame_count = 0


if SCREEN_CAPTURE_AVAILABLE:
    class FrameDelegate(NSObject):
        """处理视频帧的回调"""

        def initWithRecorder_(self, recorder):
            self = super().init()
            if self:
                self._recorder = recorder
            return self

        def captureOutput_didOutputSampleBuffer_fromConnection_(self, output, sample_buffer, connection):
            if self._recorder:
                self._recorder.process_frame(sample_buffer)


# FFmpeg 降级方案 - 使用 avfoundation 捕获屏幕区域
class FFmpegScreenRecorder:
    """FFmpeg 屏幕录制器 - 使用窗口位置裁剪屏幕区域"""

    RESOLUTIONS = {
        "原始": (0, 0),  # 使用窗口原始尺寸
        "1080p": (1920, 1080),
        "720p": (1280, 720),
    }

    def __init__(self):
        self._process = None
        self._is_recording = False
        self._output_path = ""
        self._resolution = "1080p"
        self._target_w = 1920
        self._target_h = 1080
        self._fps = 30
        self._frame_count = 0
        self._audio_path = None
        self._start_time = 0.0
        self._window_rect = None
        self._qt_window = None  # 保存 Qt 窗口引用
        self._screen_scale = 1.0  # Retina 缩放因子
        self._original_size = None  # 窗口原始尺寸（用于"原始"分辨率选项）

    def set_resolution(self, resolution: str):
        if resolution in self.RESOLUTIONS:
            self._resolution = resolution
            if resolution == "原始":
                # 原始分辨率在录制时动态设置
                pass
            else:
                self._target_w, self._target_h = self.RESOLUTIONS[resolution]

    def get_resolution(self) -> str:
        return self._resolution

    def get_resolution_size(self) -> Tuple[int, int]:
        return self._target_w, self._target_h

    def is_recording(self) -> bool:
        return self._is_recording

    def get_recording_time(self) -> float:
        if not self._is_recording or self._start_time == 0:
            return 0.0
        return time.time() - self._start_time

    def _get_screen_scale_factor(self) -> float:
        """获取屏幕缩放因子（Retina 屏幕为 2.0）"""
        try:
            if self._qt_window:
                # 使用 Qt 获取设备像素比
                return self._qt_window.devicePixelRatio()
        except:
            pass

        # 尝试从环境变量获取
        try:
            import os
            scale = os.environ.get('QT_SCALE_FACTOR', '1.0')
            return float(scale)
        except:
            pass

        return 1.0

    def _get_window_rect_macos(self, qt_window_id: int) -> Optional[Tuple[int, int, int, int]]:
        """使用 macOS API 获取窗口位置（物理像素坐标）"""
        try:
            from Quartz import (
                CGWindowListCopyWindowInfo, kCGNullWindowID,
                kCGWindowListOptionOnScreenOnly
            )

            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID
            )

            current_pid = os.getpid()

            # 首先尝试精确匹配窗口 ID
            for window_info in window_list:
                window_id = window_info.get('kCGWindowNumber', 0)
                if window_id == qt_window_id:
                    bounds = window_info.get('kCGWindowBounds', {})
                    x = int(bounds.get('X', 0))
                    y = int(bounds.get('Y', 0))
                    w = int(bounds.get('Width', 0))
                    h = int(bounds.get('Height', 0))
                    if w > 0 and h > 0:
                        print(f"[FFmpegScreenRecorder] macOS 精确匹配窗口: ({x}, {y}) 大小: {w}x{h}")
                        return (x, y, w, h)

            # 查找当前进程的可视窗口
            for window_info in window_list:
                owner_pid = window_info.get('kCGWindowOwnerPID', 0)
                if owner_pid == current_pid:
                    window_name = window_info.get('kCGWindowName', '')
                    window_id = window_info.get('kCGWindowNumber', 0)
                    # 跳过没有名称的窗口
                    if window_name and window_id > 0:
                        bounds = window_info.get('kCGWindowBounds', {})
                        x = int(bounds.get('X', 0))
                        y = int(bounds.get('Y', 0))
                        w = int(bounds.get('Width', 0))
                        h = int(bounds.get('Height', 0))
                        if w > 0 and h > 0:
                            print(f"[FFmpegScreenRecorder] macOS 进程窗口 '{window_name}': ({x}, {y}) 大小: {w}x{h}")
                            return (x, y, w, h)

            return None
        except Exception as e:
            print(f"[FFmpegScreenRecorder] macOS API 获取窗口位置失败: {e}")
            return None

    def _get_window_rect_qt(self) -> Optional[Tuple[int, int, int, int]]:
        """使用 Qt 获取窗口位置并转换为物理像素坐标"""
        try:
            if self._qt_window:
                # 获取设备像素比（Retina 屏幕为 2.0）
                scale = self._qt_window.devicePixelRatio()
                self._screen_scale = scale

                # 获取窗口几何信息（逻辑坐标）
                geo = self._qt_window.geometry()
                # 获取窗口在屏幕上的位置（包括窗口装饰）
                global_pos = self._qt_window.mapToGlobal(self._qt_window.rect().topLeft())

                # 转换为物理像素坐标
                x = int(global_pos.x() * scale)
                y = int(global_pos.y() * scale)
                w = int(geo.width() * scale)
                h = int(geo.height() * scale)

                print(f"[FFmpegScreenRecorder] Qt 窗口位置 (逻辑): ({global_pos.x()}, {global_pos.y()}) 大小: {geo.width()}x{geo.height()}")
                print(f"[FFmpegScreenRecorder] Qt 窗口位置 (物理, scale={scale}): ({x}, {y}) 大小: {w}x{h}")
                return (x, y, w, h)
            return None
        except Exception as e:
            print(f"[FFmpegScreenRecorder] Qt 获取窗口位置失败: {e}")
            return None

    def _get_avfoundation_screen_device(self, window_rect: Tuple[int, int, int, int] = None) -> Tuple[str, dict]:
        """获取 avfoundation 屏幕设备名称和屏幕信息

        Args:
            window_rect: 窗口矩形 (x, y, w, h)，用于确定窗口在哪个屏幕上

        Returns:
            (设备索引, 屏幕信息字典) 或 (None, None)
        """
        try:
            # 列出设备
            result = subprocess.run(
                ['ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', ''],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stderr

            # 查找屏幕设备
            import re
            # 匹配 [N] Capture screen X
            matches = re.findall(r'\[(\d+)\] (Capture screen \d+)', output)
            if matches:
                screen_info = None

                # 如果有窗口位置，尝试确定窗口在哪个屏幕上
                if window_rect:
                    try:
                        from AppKit import NSScreen
                        # 获取所有屏幕
                        screens = NSScreen.screens()
                        if screens:
                            wx, wy, ww, wh = window_rect
                            # 窗口中心点（macOS 坐标，原点左下角，Y向上）
                            center_x = wx + ww / 2
                            center_y = wy + wh / 2

                            print(f"[FFmpegScreenRecorder] 窗口中心点 (macOS逻辑坐标): ({center_x}, {center_y})")

                            # 主屏幕信息
                            main_screen = screens[0]

                            for i, screen in enumerate(screens):
                                frame = screen.frame()
                                sx = int(frame.origin.x)
                                sy = int(frame.origin.y)
                                sw = int(frame.size.width)
                                sh = int(frame.size.height)

                                # 获取该屏幕的缩放因子（Retina 屏幕为 2.0）
                                scale = screen.backingScaleFactor()
                                print(f"[FFmpegScreenRecorder] 屏幕 {i}: {sw}x{sh} at ({sx}, {sy}) scale={scale}")

                                # 检查窗口中心是否在屏幕内（macOS 坐标）
                                # 注意：sy 是屏幕底边的 Y 坐标
                                if (sx <= center_x < sx + sw and
                                    sy <= center_y < sy + sh):
                                    # 找到对应的 avfoundation 设备
                                    for idx, name in matches:
                                        if f"screen {i}" in name:
                                            print(f"[FFmpegScreenRecorder] 窗口在屏幕 {i} 上，使用设备: [{idx}] {name}")

                                            # 计算相对于该屏幕的坐标
                                            # ffmpeg 使用左上角为原点，Y 向下，使用物理像素
                                            # macOS 使用左下角为原点，Y 向上，使用逻辑像素

                                            # 1. 转换为相对于屏幕的坐标
                                            rel_x = (wx - sx) * scale
                                            # macOS Y 坐标从底部算起，ffmpeg 从顶部算起
                                            # 窗口顶部在 macOS 坐标中是 wy + wh
                                            # 转换: ffmpeg_y = (screen_height_logical - (wy + wh - sy)) * scale
                                            # 简化: rel_y = (sh - (wy + wh - sy)) * scale
                                            rel_y = (sh - (wy + wh - sy)) * scale
                                            rel_w = ww * scale
                                            rel_h = wh * scale

                                            screen_info = {
                                                'index': i,
                                                'x': sx,
                                                'y': sy,
                                                'width': sw,
                                                'height': sh,
                                                'scale': scale,
                                                'rel_x': int(rel_x),
                                                'rel_y': int(rel_y),
                                                'window_w': int(rel_w),
                                                'window_h': int(rel_h)
                                            }
                                            print(f"[FFmpegScreenRecorder] 物理像素坐标 (ffmpeg): ({int(rel_x)}, {int(rel_y)}) 大小: {int(rel_w)}x{int(rel_h)}")
                                            return idx, screen_info
                                    break
                    except Exception as e:
                        print(f"[FFmpegScreenRecorder] 确定屏幕失败: {e}")
                        import traceback
                        traceback.print_exc()

                # 使用第一个屏幕
                device_idx, device_name = matches[0]
                print(f"[FFmpegScreenRecorder] 找到屏幕设备: [{device_idx}] {device_name}")
                return device_idx, screen_info

            print("[FFmpegScreenRecorder] 未找到屏幕设备")
            return None, None
        except Exception as e:
            print(f"[FFmpegScreenRecorder] 获取设备列表失败: {e}")
            return None, None

    def start_desktop(self, output_path: str, audio_path: str = None) -> bool:
        """录制当前主显示器桌面

        Args:
            output_path: 输出视频路径
            audio_path: 音频文件路径
        """
        try:
            self._audio_path = audio_path
            self._output_path = output_path
            self._frame_count = 0

            # 创建输出目录
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # 获取主显示器设备索引
            screen_device = self._get_main_screen_device()
            if screen_device is None:
                print("[FFmpegScreenRecorder] 未找到屏幕设备")
                return False

            # 获取主显示器分辨率
            screen_w, screen_h = self._get_main_screen_size()
            print(f"[FFmpegScreenRecorder] 主显示器分辨率: {screen_w}x{screen_h}")

            # 确定输出分辨率
            if self._resolution == "原始":
                output_w, output_h = screen_w, screen_h
                print(f"[FFmpegScreenRecorder] 使用原始分辨率: {output_w}x{output_h}")
                # 原始分辨率不需要 scale
                filter_str = None
            else:
                output_w, output_h = self._target_w, self._target_h
                # 保持宽高比缩放
                filter_str = f'scale={output_w}:{output_h}:force_original_aspect_ratio=decrease,pad={output_w}:{output_h}:(ow-iw)/2:(oh-ih)/2'

            ffmpeg_cmd = [
                'ffmpeg',
                '-y',
                '-f', 'avfoundation',
                '-framerate', str(self._fps),
                '-capture_cursor', 'true',  # 捕获光标
                '-i', screen_device,
            ]

            if filter_str:
                ffmpeg_cmd.extend(['-filter:v', filter_str])

            ffmpeg_cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-crf', '18',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                output_path
            ])

            print(f"[FFmpegScreenRecorder] 启动命令: {' '.join(ffmpeg_cmd)}")

            self._process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            self._is_recording = True
            self._start_time = time.time()
            print(f"[FFmpegScreenRecorder] 开始录制桌面: {output_path}")
            return True

        except Exception as e:
            print(f"[FFmpegScreenRecorder] 启动失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_main_screen_device(self) -> Optional[str]:
        """获取主显示器设备索引"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', ''],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stderr

            import re
            matches = re.findall(r'\[(\d+)\] (Capture screen \d+)', output)
            if matches:
                device_idx, device_name = matches[0]
                print(f"[FFmpegScreenRecorder] 使用主显示器: [{device_idx}] {device_name}")
                return device_idx

            print("[FFmpegScreenRecorder] 未找到屏幕设备")
            return None
        except Exception as e:
            print(f"[FFmpegScreenRecorder] 获取设备列表失败: {e}")
            return None

    def _get_main_screen_size(self) -> Tuple[int, int]:
        """获取主显示器分辨率（物理像素）"""
        try:
            from AppKit import NSScreen
            main_screen = NSScreen.mainScreen()
            if main_screen:
                frame = main_screen.frame()
                scale = main_screen.backingScaleFactor()
                w = int(frame.size.width * scale)
                h = int(frame.size.height * scale)
                return w, h
        except Exception as e:
            print(f"[FFmpegScreenRecorder] 获取主显示器分辨率失败: {e}")

        # 默认返回 1080p
        return 1920, 1080

    def start(self, qt_window_id: int, output_path: str, audio_path: str = None, qt_window=None, window_info: WindowInfo = None) -> bool:
        """使用 ffmpeg 的 avfoundation 输入捕获特定窗口区域

        Args:
            qt_window_id: Qt 窗口 ID
            output_path: 输出视频路径
            audio_path: 音频文件路径
            qt_window: Qt 窗口对象（用于获取位置）
            window_info: 直接指定的窗口信息（优先使用）
        """
        try:
            self._audio_path = audio_path
            self._output_path = output_path
            self._frame_count = 0
            self._qt_window = qt_window

            # 尝试多种方式获取窗口位置
            window_rect = None

            # 方法1: 直接使用指定的窗口信息
            if window_info:
                window_rect = (window_info.x, window_info.y, window_info.width, window_info.height)
                print(f"[FFmpegScreenRecorder] 使用指定窗口: {window_info.title} ({window_info.owner_name})")
                print(f"[FFmpegScreenRecorder] 窗口位置 (macOS坐标): ({window_info.x}, {window_info.y}) 大小: {window_info.width}x{window_info.height}")

            # 方法2: 使用 macOS API
            if window_rect is None and IS_MACOS:
                window_rect = self._get_window_rect_macos(qt_window_id)

            # 方法3: 使用 Qt 窗口对象
            if window_rect is None and qt_window:
                window_rect = self._get_window_rect_qt()

            if window_rect is None:
                print("[FFmpegScreenRecorder] 无法获取窗口位置")
                return False

            x, y, w, h = window_rect
            self._window_rect = window_rect

            # 创建输出目录
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # 获取屏幕设备索引和坐标转换信息
            screen_device, screen_info = self._get_avfoundation_screen_device(window_rect)
            if screen_device is None:
                print("[FFmpegScreenRecorder] 未找到屏幕设备")
                return False

            # 确定录制坐标
            if screen_info:
                # 使用转换后的相对坐标（针对多显示器）
                crop_x = int(screen_info['rel_x'])
                crop_y = int(screen_info['rel_y'])
                crop_w = int(screen_info['window_w'])
                crop_h = int(screen_info['window_h'])
                print(f"[FFmpegScreenRecorder] crop 坐标: ({crop_x}, {crop_y}) 大小: {crop_w}x{crop_h}")
            else:
                # 单显示器，直接使用原始坐标
                crop_x, crop_y, crop_w, crop_h = x, y, w, h
                print(f"[FFmpegScreenRecorder] 单显示器模式，crop 坐标: ({crop_x}, {crop_y}) 大小: {crop_w}x{crop_h}")

            # 确定输出分辨率
            if self._resolution == "原始":
                # 使用窗口原始尺寸
                output_w, output_h = crop_w, crop_h
                print(f"[FFmpegScreenRecorder] 使用原始分辨率: {output_w}x{output_h}")
            else:
                output_w, output_h = self._target_w, self._target_h

            # 使用 avfoundation 捕获屏幕特定区域
            # -filter:v crop=... 裁剪到窗口区域
            # 如果原始尺寸和输出尺寸相同，不需要 scale
            if crop_w == output_w and crop_h == output_h:
                filter_str = f'crop={crop_w}:{crop_h}:{crop_x}:{crop_y}'
            else:
                filter_str = f'crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={output_w}:{output_h}'

            ffmpeg_cmd = [
                'ffmpeg',
                '-y',
                '-f', 'avfoundation',
                '-framerate', str(self._fps),
                '-capture_cursor', 'false',  # 不捕获光标
                '-i', screen_device,  # 使用正确的屏幕设备索引
                '-filter:v', filter_str,
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-crf', '18',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                output_path
            ]

            print(f"[FFmpegScreenRecorder] 启动命令: {' '.join(ffmpeg_cmd)}")

            self._process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            self._is_recording = True
            self._start_time = time.time()
            print(f"[FFmpegScreenRecorder] 开始录制: {output_path}")
            return True

        except Exception as e:
            print(f"[FFmpegScreenRecorder] 启动失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def stop(self) -> Tuple[bool, str, int]:
        if not self._is_recording:
            return False, "", 0

        self._is_recording = False

        if self._process:
            try:
                # 发送 'q' 命令给 ffmpeg 优雅退出
                print("[FFmpegScreenRecorder] 正在停止录制...")
                try:
                    self._process.stdin.write(b'q')
                    self._process.stdin.flush()
                except:
                    pass  # stdin 可能已关闭

                # 关闭 stdin
                try:
                    self._process.stdin.close()
                except:
                    pass

                # 等待 ffmpeg 完成
                stdout, stderr = self._process.communicate(timeout=15)
            except Exception as e:
                print(f"[FFmpegScreenRecorder] 停止时出错: {e}")
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except:
                    try:
                        self._process.kill()
                        self._process.wait(timeout=2)
                    except:
                        pass
            finally:
                self._process = None

        path = self._output_path
        frames = self._frame_count

        # 合并音频
        if self._audio_path and path and os.path.exists(path):
            self._merge_audio(path, self._audio_path)

        duration = time.time() - self._start_time if self._start_time > 0 else 0
        print(f"[FFmpegScreenRecorder] 完成: {path}, 时长: {duration:.1f}秒")
        return True, path, frames

    def _merge_audio(self, video_path: str, audio_path: str):
        if not os.path.exists(audio_path):
            return

        try:
            base, ext = os.path.splitext(video_path)
            merged_path = f"{base}_audio{ext}"

            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                merged_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=60)

            if result.returncode == 0 and os.path.exists(merged_path):
                os.remove(video_path)
                os.rename(merged_path, video_path)
                print(f"[FFmpegScreenRecorder] 音频合并完成")
            else:
                if os.path.exists(merged_path):
                    os.remove(merged_path)
        except Exception as e:
            print(f"[FFmpegScreenRecorder] 音频合并出错: {e}")


# 选择可用的录屏器
# 优先使用 FFmpeg 方案，因为它更简单可靠
DefaultScreenRecorder = FFmpegScreenRecorder

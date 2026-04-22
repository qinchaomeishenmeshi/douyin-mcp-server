# -*- coding: utf-8 -*-
"""
ASR语音识别处理模块 - FunASR集成版本
"""

import os
import json
import time
import subprocess
import re
import threading
import queue
import uuid
import warnings
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from utils.logger import logger

# 抑制 transformers 的警告
warnings.filterwarnings(
    "ignore", message=".*The attention mask and the pad token id were not set.*"
)
warnings.filterwarnings(
    "ignore", message=".*Setting `pad_token_id` to `eos_token_id`.*"
)

try:
    from funasr import AutoModel
    import torch
    import torchaudio
    import ffmpeg
    import librosa
    import soundfile as sf
    import numpy as np

    # 尝试抑制 transformers 日志
    try:
        import transformers

        transformers.logging.set_verbosity_error()
    except ImportError:
        pass

    FUNASR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[ASR] FunASR相关依赖未安装: {e}")
    FUNASR_AVAILABLE = False


class FunASRProcessor:
    """基于FunASR的语音识别处理器"""

    def __init__(
        self,
        model_name: str = "FunAudioLLM/Fun-ASR-Nano-2512",
        device: str = "auto",
        batch_size: int = 64,
        vad_model: str = "fsmn-vad",
        punc_model: str = "ct-punc",
        output_formats: list = None,
    ):
        """
        初始化FunASR处理器

        Args:
            model_name: ASR模型名称，默认使用FunASR-Nano
            device: 设备类型 ("auto", "cpu", "cuda")
            batch_size: 批处理大小
            vad_model: VAD模型名称
            punc_model: 标点符号模型名称
            output_formats: 输出格式列表，默认为["txt"]
        """
        self.model_name = model_name
        self.device = self._get_device(device)
        self.batch_size = batch_size
        self.vad_model = vad_model
        self.punc_model = punc_model
        self.output_formats = output_formats or ["txt"]
        self.supported_formats = [".mp3", ".wav", ".m4a", ".flac", ".aac"]

        # 模型实例（延迟加载）
        self._model = None
        self._model_loaded = False
        self._model_load_lock = threading.Lock()  # 为模型加载添加专用的锁

        logger.info(
            f"[ASR] FunASR处理器初始化完成 - 模型: {model_name}, 设备: {self.device}"
        )

    def clean_asr_text(self, text: str) -> str:
        """清理ASR文本中的标签和元数据

        Args:
            text: 原始ASR文本

        Returns:
            str: 清理后的纯文本
        """
        if not text:
            return ""

        # 移除各种ASR标签
        # 匹配模式: < | tag | >, < | tag1 | tag2 | >, 等
        tag_pattern = r"<\s*\|[^|]*\|\s*>"
        cleaned_text = re.sub(tag_pattern, "", text)

        # 移除多余的空格和标点符号
        cleaned_text = re.sub(r"\s+", " ", cleaned_text)  # 多个空格合并为一个
        cleaned_text = re.sub(r"，{2,}", "，", cleaned_text)  # 多个逗号合并为一个
        cleaned_text = re.sub(r"。{2,}", "。", cleaned_text)  # 多个句号合并为一个

        # 去除首尾空格
        cleaned_text = cleaned_text.strip()

        logger.debug(f"[ASR] 文本清理: '{text[:50]}...' -> '{cleaned_text[:50]}...'")

        return cleaned_text

    def _get_device(self, device: str) -> str:
        """获取可用设备

        注意: FunASR 库 (cif_predictor.py) 内部使用了 torch.float64，
        但 Apple MPS 框架不支持 float64。因此禁用 MPS 自动检测，
        Mac 用户将自动回退到 CPU。
        """
        if device == "auto":
            if torch.cuda.is_available():
                return "cuda"
            # MPS 不支持 float64，FunASR 库会报错，强制使用 CPU
            # elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            #     return "mps"
            else:
                return "cpu"
        # 如果用户显式指定了 mps，给出警告并回退到 cpu
        if device == "mps":
            logger.warning("[ASR] MPS 设备不支持 FunASR (float64 限制)，自动回退到 CPU")
            return "cpu"
        return device

    def _load_model(self) -> bool:
        """延迟加载ASR模型（线程安全）"""
        # 使用双重检查锁定模式确保线程安全和高性能
        if self._model_loaded:
            return True

        with self._model_load_lock:
            # 再次检查，防止在等待锁的过程中模型已被其他线程加载
            if self._model_loaded:
                return True

            if not FUNASR_AVAILABLE:
                logger.error("[ASR] FunASR依赖未安装，无法加载模型")
                return False

            try:
                logger.info(
                    f"[ASR] 正在加载模型: {self.model_name} (此过程可能需要下载数GB模型文件，请耐心等待)"
                )
                start_time = time.time()

                # 初始化模型参数
                model_kwargs = {
                    "model": self.model_name,
                    "device": self.device,
                    "batch_size": self.batch_size,
                    "disable_update": True,  # 禁用自动更新
                }

                # FunASR-Nano 特殊处理
                if "Fun-ASR-Nano" in self.model_name:
                    model_kwargs["trust_remote_code"] = True
                    model_kwargs["batch_size"] = 1  # FunASR-Nano 目前不支持批处理
                    # 获取项目根目录下的 lib/fun_asr_nano/model.py 路径
                    try:
                        project_root = Path(__file__).resolve().parent.parent.parent
                        remote_code_path = (
                            project_root / "lib" / "fun_asr_nano" / "model.py"
                        )
                        if remote_code_path.exists():
                            model_kwargs["remote_code"] = str(remote_code_path)
                            logger.info(
                                f"[ASR] 使用本地代码加载模型: {remote_code_path}"
                            )
                        else:
                            logger.warning(
                                f"[ASR] 未找到本地模型代码: {remote_code_path}，尝试自动下载"
                            )
                    except Exception as e:
                        logger.warning(f"[ASR] 解析本地模型代码路径失败: {e}")

                # 添加VAD模型（如果指定）
                if self.vad_model:
                    model_kwargs["vad_model"] = self.vad_model
                    # 使用更宽松的VAD设置，避免错误
                    model_kwargs["vad_kwargs"] = {
                        "max_single_segment_time": 30000,  # 更长的单段时间
                        "max_end_silence_time": 1000,  # 更长的结束静音时间
                        "max_start_silence_time": 1000,  # 更长的开始静音时间
                        "speech_noise_threshold": 0.6,  # 更宽松的语音噪声阈值
                    }

                # 添加标点符号模型（如果指定）
                if self.punc_model:
                    model_kwargs["punc_model"] = self.punc_model

                # 尝试加载模型
                try:
                    self._model = AutoModel(**model_kwargs)
                except Exception as e:
                    logger.error(f"[ASR] 使用默认参数加载模型失败: {str(e)}")

                    # 尝试使用简化参数
                    logger.info("[ASR] 尝试使用简化参数加载模型...")
                    simplified_kwargs = {
                        "model": self.model_name,
                        "device": self.device,
                        "disable_update": True,
                    }

                    # FunASR-Nano 特殊处理
                    if "Fun-ASR-Nano" in self.model_name:
                        simplified_kwargs["trust_remote_code"] = True
                        simplified_kwargs["batch_size"] = 1
                        if "remote_code" in model_kwargs:
                            simplified_kwargs["remote_code"] = model_kwargs[
                                "remote_code"
                            ]

                    # 如果是GPU错误，尝试回退到CPU
                    if "CUDA" in str(e) and self.device in ["cuda", "auto"]:
                        logger.info("[ASR] 检测到CUDA错误，尝试使用CPU设备")
                        simplified_kwargs["device"] = "cpu"
                        self.device = "cpu"  # 更新实例设备类型

                    self._model = AutoModel(**simplified_kwargs)
                    logger.info("[ASR] 使用简化参数成功加载模型")

                load_time = time.time() - start_time
                self._model_loaded = True
                logger.info(f"[ASR] 模型加载完成，耗时: {load_time:.2f}秒")
                return True

            except Exception as e:
                logger.error(f"[ASR] 模型加载失败: {str(e)}", exc_info=True)
                self._model_loaded = False  # 确保加载失败后状态正确

                # 尝试加载备用模型
                if (
                    self.model_name
                    != "iic/speech_paraformer_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
                ):
                    logger.info(
                        "[ASR] 尝试加载备用模型: iic/speech_paraformer_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
                    )
                    try:
                        self.model_name = "iic/speech_paraformer_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
                        return self._load_model()  # 递归调用，尝试加载备用模型
                    except Exception as backup_e:
                        logger.error(f"[ASR] 备用模型加载也失败: {str(backup_e)}")

                return False

    def is_supported_format(self, file_path: str) -> bool:
        """检查文件格式是否支持ASR处理"""
        return Path(file_path).suffix.lower() in self.supported_formats

    def extract_audio_from_video(
        self, video_path: str, audio_path: str, sample_rate: int = 16000
    ) -> bool:
        """从视频中提取音频"""
        try:
            logger.info(f"[ASR] 开始提取音频: {video_path} -> {audio_path}")

            # 确保输出目录存在
            Path(audio_path).parent.mkdir(parents=True, exist_ok=True)

            # 使用ffmpeg提取音频
            (
                ffmpeg.input(video_path)
                .output(
                    audio_path,
                    acodec="pcm_s16le",  # 16位PCM编码
                    ac=1,  # 单声道 (修改为单声道以提高ASR性能)
                    ar=sample_rate,
                )  # 采样率
                .overwrite_output()  # 覆盖输出文件
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )

            if Path(audio_path).exists():
                logger.info(f"[ASR] 音频提取成功: {audio_path}")
                return True
            else:
                logger.error(f"[ASR] 音频提取失败: 输出文件不存在")
                return False

        except ffmpeg.Error as e:
            logger.error(
                f"[ASR] FFmpeg音频提取失败: {e.stderr.decode() if e.stderr else str(e)}"
            )
            return False
        except Exception as e:
            logger.error(f"[ASR] 音频提取异常: {str(e)}")
            return False

    def preprocess_audio(
        self, audio_path: str, target_sample_rate: int = 16000
    ) -> Optional[str]:
        """预处理音频文件"""
        try:
            # 检查音频文件信息
            audio_info = sf.info(audio_path)
            logger.info(
                f"[ASR] 音频信息: 采样率={audio_info.samplerate}Hz, 声道数={audio_info.channels}, 时长={audio_info.duration:.2f}秒"
            )

            # 如果音频已经符合要求，直接返回
            if audio_info.samplerate == target_sample_rate and audio_info.channels == 1:
                return audio_path

            # 需要重新采样或转换声道
            processed_path = str(Path(audio_path).with_suffix(".processed.wav"))

            # 读取音频
            audio_data, sr = librosa.load(audio_path, sr=target_sample_rate, mono=True)

            # 保存处理后的音频
            sf.write(processed_path, audio_data, target_sample_rate)

            logger.info(f"[ASR] 音频预处理完成: {processed_path}")
            return processed_path

        except Exception as e:
            logger.error(f"[ASR] 音频预处理失败: {str(e)}")
            return None

    def transcribe_audio(
        self, audio_path: str, language: str = "auto"
    ) -> Optional[Dict[str, Any]]:
        """使用FunASR将音频转换为文字"""
        if not self._load_model():
            logger.error("[ASR] 无法加载ASR模型，转写失败")
            return None

        try:
            logger.info(f"[ASR] 开始语音识别: {audio_path}")
            start_time = time.time()

            # 检查文件是否存在
            if not Path(audio_path).exists():
                logger.error(f"[ASR] 音频文件不存在: {audio_path}")
                return None

            # 检查文件格式
            if not self.is_supported_format(audio_path):
                logger.warning(
                    f"[ASR] 不支持的音频格式: {Path(audio_path).suffix}, 尝试进行处理"
                )

            # 预处理音频
            processed_audio = self.preprocess_audio(audio_path)
            if not processed_audio:
                logger.error(f"[ASR] 音频预处理失败: {audio_path}")
                return None

            # 执行语音识别
            try:
                generate_kwargs = {
                    "input": str(processed_audio),
                    "language": language,
                    "use_itn": True,  # 使用逆文本标准化
                    "merge_vad": True,  # 合并VAD结果
                    "merge_length_s": 15,  # 合并长度（秒）
                }

                # FunASR-Nano 不支持批处理，必须强制 batch_size=1
                if "Fun-ASR-Nano" in self.model_name:
                    generate_kwargs["batch_size"] = 1
                else:
                    generate_kwargs["batch_size_s"] = 300  # 批处理大小（秒）

                result = self._model.generate(**generate_kwargs)
            except Exception as e:
                logger.error(f"[ASR] 模型推理失败: {str(e)}", exc_info=True)
                # 尝试使用不同的参数重试一次
                try:
                    logger.info("[ASR] 尝试使用备用参数重新识别...")

                    retry_kwargs = {
                        "input": str(processed_audio),
                        "language": language,
                        "use_itn": True,
                        "merge_vad": False,  # 禁用VAD合并
                    }

                    if "Fun-ASR-Nano" in self.model_name:
                        retry_kwargs["batch_size"] = 1
                    else:
                        retry_kwargs["batch_size_s"] = 100

                    result = self._model.generate(**retry_kwargs)
                except Exception as retry_e:
                    logger.error(f"[ASR] 重试识别也失败: {str(retry_e)}")
                    return None

            process_time = time.time() - start_time

            if result and len(result) > 0:
                # 提取识别结果
                transcription_data = {
                    "text": "",
                    "segments": [],
                    "language": language,
                    "duration": 0,
                    "process_time": process_time,
                }

                # 处理结果格式 (增加健壮性检查)
                if (
                    isinstance(result, list)
                    and len(result) > 0
                    and isinstance(result[0], dict)
                ):
                    full_text = result[0].get("text", "")
                    segments = result[0].get("segments", [])

                    transcription_data["text"] = self.clean_asr_text(full_text)
                    transcription_data["segments"] = segments
                    transcription_data["language"] = result[0].get("language", language)

                    try:
                        transcription_data["duration"] = librosa.get_duration(
                            path=processed_audio
                        )
                    except Exception as e:
                        logger.warning(f"[ASR] 无法获取音频时长: {e}")
                        transcription_data["duration"] = 0
                else:
                    logger.warning(f"[ASR] 识别结果格式不符合预期: {result}")

                logger.info(
                    f"[ASR] 语音识别完成，耗时: {process_time:.2f}秒, 文本长度: {len(transcription_data['text'])}字符"
                )
                if transcription_data["text"]:
                    logger.info(
                        f"[ASR] 识别结果摘要: '{transcription_data['text'][:50]}...'"
                    )
                else:
                    logger.warning("[ASR] 识别结果为空")

                # 清理临时文件
                if processed_audio != audio_path and Path(processed_audio).exists():
                    try:
                        Path(processed_audio).unlink()
                    except Exception as e:
                        logger.warning(f"[ASR] 无法删除临时处理文件: {e}")

                return transcription_data

            else:
                # 处理静音或无法识别的情况
                logger.warning(f"[ASR] 未识别到任何文本: {audio_path}")
                try:
                    duration = librosa.get_duration(path=processed_audio)
                except:
                    duration = 0

                return {
                    "text": "",
                    "segments": [],
                    "language": language,
                    "duration": duration,
                    "process_time": process_time,
                }

        except Exception as e:
            logger.error(f"[ASR] 语音识别失败: {str(e)}", exc_info=True)
            return None

    def save_transcription(
        self,
        transcription_data: Dict[str, Any],
        output_path: str,
        format_type: str = "txt",
    ) -> bool:
        """保存转换后的文字到文件"""
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            if format_type == "json":
                # 保存为JSON格式（包含时间戳等详细信息）
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(transcription_data, f, ensure_ascii=False, indent=2)
            elif format_type == "srt":
                # 保存为SRT字幕格式
                self._save_as_srt(transcription_data, output_path)
            else:
                # 默认保存为纯文本格式
                text_content = transcription_data.get("text", "")
                # 再次清理文本，确保没有遗漏的标签
                cleaned_text = self.clean_asr_text(text_content)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(cleaned_text)

            logger.info(f"[ASR] 转换结果已保存: {output_path}")
            return True

        except Exception as e:
            logger.error(f"[ASR] 保存转换结果失败: {str(e)}")
            return False

    def _save_as_srt(self, transcription_data: Dict[str, Any], output_path: str):
        """保存为SRT字幕格式"""
        with open(output_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(transcription_data.get("segments", []), 1):
                start_time = self._format_srt_time(segment.get("start", 0))
                end_time = self._format_srt_time(segment.get("end", 0))
                text = segment.get("text", "").strip()

                if text:
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{text}\n\n")

    def _format_srt_time(self, seconds: float) -> str:
        """格式化SRT时间戳"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

    def process_media_file(
        self,
        media_path: str,
        output_dir: str,
        language: str = "auto",
        save_formats: List[str] = None,
        audio_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理单个媒体文件（视频或音频）

        Args:
            media_path: 媒体文件路径
            output_dir: 输出目录
            language: 语言
            save_formats: 保存格式列表
            audio_file: (可选) 预先下载的音频文件路径，如果提供则优先使用

        Returns:
            处理结果字典
        """
        if not self._load_model():
            return {"status": "failed", "reason": "模型加载失败"}

        media_path = Path(media_path)
        if not media_path.exists():
            return {"status": "failed", "reason": f"媒体文件不存在: {media_path}"}

        temp_audio_path = None
        input_audio_path = None

        try:
            # 优先使用提供的独立音频文件
            if audio_file and Path(audio_file).exists():
                logger.info(f"[ASR] 使用预先下载的音频文件: {audio_file}")
                input_audio_path = audio_file
            # 其次，如果输入是支持的音频格式，直接使用
            elif self.is_supported_format(str(media_path)):
                logger.info(f"[ASR] 直接处理支持的音频文件: {media_path}")
                input_audio_path = str(media_path)
            # 最后，如果输入是视频，则提取音频
            elif media_path.suffix.lower() in [".mp4", ".mov"]:
                temp_audio_path = Path(output_dir) / f"{media_path.stem}_temp_audio.wav"
                if not self.extract_audio_from_video(
                    str(media_path), str(temp_audio_path)
                ):
                    return {"status": "failed", "reason": "从视频提取音频失败"}
                input_audio_path = temp_audio_path
            else:
                return {
                    "status": "failed",
                    "reason": f"不支持的文件格式: {media_path.suffix}",
                }

            # 语音识别
            transcription_data = self.transcribe_audio(
                input_audio_path, language=language
            )

            if not transcription_data:
                return {"status": "failed", "reason": "语音识别失败"}

            # 保存转写结果
            output_base_name = media_path.stem
            saved_files = []

            formats_to_save = (
                save_formats if save_formats is not None else self.output_formats
            )

            for format_type in formats_to_save:
                output_path = (
                    Path(output_dir) / f"{output_base_name}.{format_type.lower()}"
                )
                if self.save_transcription(
                    transcription_data, str(output_path), format_type
                ):
                    saved_files.append(str(output_path))

            transcription_data["saved_files"] = saved_files
            transcription_data["status"] = "success"

            return transcription_data

        except Exception as e:
            logger.exception(f"[ASR] 处理文件时发生未知异常: {media_path}")
            return {"status": "failed", "reason": f"未知异常: {e}"}

        finally:
            # 清理临时文件
            if temp_audio_path and temp_audio_path.exists():
                try:
                    temp_audio_path.unlink()
                    logger.info(f"[ASR] 已删除临时音频文件: {temp_audio_path}")
                except Exception as e:
                    logger.error(f"[ASR] 删除临时文件失败: {e}")

    def process_directory(
        self, directory: str, language: str = "auto", save_formats: List[str] = None
    ) -> Dict[str, Any]:
        """批量处理目录中的媒体文件"""
        if save_formats is None:
            save_formats = self.output_formats

        results = {
            "total_files": 0,
            "processed_files": 0,
            "success_files": 0,
            "failed_files": 0,
            "total_time": 0,
            "details": [],
        }

        start_time = time.time()

        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                logger.error(f"[ASR] 目录不存在: {directory}")
                return results

            # 查找所有支持的媒体文件
            media_files = []
            for ext in self.supported_formats:
                media_files.extend(dir_path.rglob(f"*{ext}"))

            results["total_files"] = len(media_files)
            logger.info(f"[ASR] 找到 {len(media_files)} 个媒体文件待处理")

            for media_file in media_files:
                logger.info(
                    f"[ASR] 处理文件 ({results['processed_files']+1}/{len(media_files)}): {media_file.name}"
                )

                result = self.process_media_file(
                    str(media_file), str(media_file.parent), language, save_formats
                )

                results["details"].append(result)
                results["processed_files"] += 1

                if result["status"] == "success":
                    results["success_files"] += 1
                    logger.info(f"[ASR] 文件处理成功: {media_file.name}")
                else:
                    results["failed_files"] += 1
                    logger.warning(
                        f"[ASR] 文件处理失败: {media_file.name}, 错误: {result['reason']}"
                    )

            results["total_time"] = time.time() - start_time
            logger.info(
                f"[ASR] 批量处理完成: 总计{results['total_files']}个文件，成功{results['success_files']}个，失败{results['failed_files']}个，总耗时{results['total_time']:.2f}秒"
            )

        except Exception as e:
            logger.error(f"[ASR] 批量处理异常: {str(e)}")

        return results


# 向后兼容的ASRProcessor类
class ASRProcessor(FunASRProcessor):
    """ASR处理器 - 兼容旧版本接口"""

    def __init__(self):
        super().__init__()
        logger.info("[ASR] 使用FunASR处理器（兼容模式）")

    def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """兼容旧版本接口 - 返回纯文本"""
        result = super().transcribe_audio(audio_path)
        if result and isinstance(result, dict):
            return result.get("text", "")
        return None

    def save_transcription(self, text: str, output_path: str) -> bool:
        """兼容旧版本接口 - 保存纯文本"""
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"[ASR] 转换文本已保存: {output_path}")
            return True
        except Exception as e:
            logger.error(f"[ASR] 保存转换文本失败: {str(e)}")
            return False


# 全局ASR处理器实例字典和锁
_processors: Dict[str, FunASRProcessor] = {}
_processors_lock = threading.Lock()


def get_asr_processor(
    model_name: str = "FunAudioLLM/Fun-ASR-Nano-2512", device: str = "auto"
) -> FunASRProcessor:
    """
    获取FunASR处理器的共享实例。
    为每个模型配置（model_name, device）创建一个独立的、可复用的实例。
    这避免了在多任务并发时因配置不同而导致的模型重载问题。

    Args:
        model_name: ASR模型名称
        device: 设备类型 ("auto", "cpu", "cuda", "mps")

    Returns:
        FunASRProcessor实例
    """
    config_key = f"{model_name}-{device}"

    # 首先，在无锁的情况下快速检查实例是否存在
    if config_key in _processors:
        return _processors[config_key]

    # 如果实例不存在，则加锁创建
    with _processors_lock:
        # 再次检查，防止在等待锁的过程中实例已被其他线程创建
        if config_key in _processors:
            return _processors[config_key]

        logger.info(f"[ASR] 创建新的ASR处理器实例 for config: {config_key}")
        try:
            processor = FunASRProcessor(model_name=model_name, device=device)
            # 确保模型被加载
            if not processor._load_model():
                raise RuntimeError("模型加载失败")
            _processors[config_key] = processor
            return processor
        except Exception as e:
            logger.critical(f"[ASR] 创建ASR处理器失败 for config {config_key}: {e}")
            # 如果是CUDA错误，尝试回退到CPU
            if "CUDA" in str(e) and device in ["cuda", "auto"]:
                logger.info("[ASR] 检测到CUDA错误，尝试使用CPU设备")
                return get_asr_processor(model_name, "cpu")
            raise e


# --- 并发处理模块 ---

# 全局任务队列和结果存储
task_queue = queue.Queue()
task_results: Dict[str, Dict] = {}
_worker_threads = []
_worker_lock = threading.Lock()
_MAX_CONCURRENT_WORKERS = 2  # 默认并发工作线程数


def asr_worker():
    """后台工作者线程，从队列中获取并处理ASR任务"""
    logger.info("[ASR Worker] 工作者线程已启动")

    while True:
        try:
            task_id, audio_path, output_formats, model_name, device = task_queue.get()
            logger.info(
                f"[ASR Worker] 收到新任务: {task_id}, 文件: {Path(audio_path).name}"
            )

            # 更新任务状态为处理中
            task_results[task_id].update({"status": "processing"})

            # 为每个任务获取或复用一个处理器实例
            processor = get_asr_processor(model_name=model_name, device=device)

            result = _process_single_file_core(
                processor=processor,
                audio_path=audio_path,
                output_formats=output_formats,
            )

            task_results[task_id].update({"status": "completed", "data": result})
            logger.info(f"[ASR Worker] 任务完成: {task_id}")

        except Exception as e:
            if "task_id" in locals():
                task_results[task_id] = {"status": "failed", "reason": str(e)}
                logger.error(
                    f"[ASR Worker] 任务失败: {task_id}, 错误: {e}", exc_info=True
                )
        finally:
            task_queue.task_done()


def start_asr_worker(num_workers: int = _MAX_CONCURRENT_WORKERS):
    """启动后台ASR工作者线程（如果尚未启动）

    Args:
        num_workers: 工作者线程数量
    """
    global _worker_threads
    with _worker_lock:
        if not _worker_threads or all(not t.is_alive() for t in _worker_threads):
            _worker_threads.clear()
            for i in range(num_workers):
                worker = threading.Thread(
                    target=asr_worker, daemon=True, name=f"ASR-Worker-{i}"
                )
                worker.start()
                _worker_threads.append(worker)
            logger.info(f"[ASR] 已启动 {num_workers} 个后台工作者线程")
        elif len(_worker_threads) < num_workers:
            current_count = len([t for t in _worker_threads if t.is_alive()])
            for i in range(current_count, num_workers):
                worker = threading.Thread(
                    target=asr_worker, daemon=True, name=f"ASR-Worker-{i}"
                )
                worker.start()
                _worker_threads.append(worker)
            logger.info(f"[ASR] 已将工作者线程数量增加到 {num_workers}")


def submit_asr_task(
    audio_path: str,
    output_formats: List[str],
    model_name: str = "FunAudioLLM/Fun-ASR-Nano-2512",
    device: str = "auto",
) -> str:
    """
    提交一个新的ASR任务到队列中。

    Args:
        audio_path: 音频文件路径
        output_formats: 输出格式列表
        model_name: 模型名称
        device: 设备类型

    Returns:
        str: 唯一任务ID
    """
    # 确保工作者线程正在运行
    start_asr_worker()

    task_id = str(uuid.uuid4())
    task = (task_id, audio_path, output_formats, model_name, device)
    task_queue.put(task)

    # 初始化任务状态
    task_results[task_id] = {"status": "queued", "file_path": audio_path}
    logger.info(f"[ASR] 新任务已入队: {task_id}, 文件: {Path(audio_path).name}")

    return task_id


def get_asr_task_status(task_id: str) -> Dict[str, Any]:
    """
    根据任务ID获取ASR任务的状态和结果。

    Args:
        task_id: 任务ID

    Returns:
        Dict: 任务状态和结果的字典
    """
    return task_results.get(task_id, {"status": "not_found", "reason": "任务ID不存在"})


def create_batch_task(
    file_paths: List[str],
    output_formats: List[str],
    model_name: str = "FunAudioLLM/Fun-ASR-Nano-2512",
    device: str = "auto",
    batch_name: str = None,
) -> str:
    """
    批量提交ASR任务

    Args:
        file_paths: 文件路径列表
        output_formats: 输出格式列表
        model_name: 模型名称
        device: 设备类型
        batch_name: 批量任务名称

    Returns:
        str: 批量任务ID
    """
    task_ids = []
    for file_path in file_paths:
        task_id = submit_asr_task(
            audio_path=file_path,
            output_formats=output_formats,
            model_name=model_name,
            device=device,
        )
        task_ids.append(task_id)

    return _batch_manager.create_batch(task_ids, batch_name)


def get_batch_task_status(batch_id: str) -> Dict[str, Any]:
    """获取批量任务状态"""
    return _batch_manager.get_batch_status(batch_id)


def get_all_batch_tasks() -> List[Dict]:
    """获取所有批量任务"""
    return _batch_manager.get_all_batches()


def cancel_task(task_id: str) -> bool:
    """
    取消单个任务（标记为失败）

    Args:
        task_id: 任务ID

    Returns:
        bool: 是否成功取消
    """
    if task_id in task_results:
        task_results[task_id]["status"] = "failed"
        task_results[task_id]["reason"] = "用户取消"
        logger.info(f"[ASR] 任务已取消: {task_id}")
        return True
    return False


def cancel_batch_task(batch_id: str) -> int:
    """
    取消批量任务（取消所有未完成的子任务）

    Args:
        batch_id: 批量任务ID

    Returns:
        int: 成功取消的任务数量
    """
    batch = _batch_manager.get_batch_status(batch_id)
    if batch.get("status") == "not_found":
        return 0

    task_ids = batch.get("task_ids", [])
    cancelled_count = 0
    for task_id in task_ids:
        status = task_results.get(task_id, {}).get("status")
        if status in ["queued", "processing"]:
            if cancel_task(task_id):
                cancelled_count += 1

    return cancelled_count


# --- 批量任务管理 ---


class BatchASRManager:
    """批量ASR任务管理器"""

    def __init__(self):
        self.batch_tasks: Dict[str, Dict] = {}  # batch_id -> batch_info
        self.lock = threading.Lock()

    def create_batch(self, task_ids: List[str], batch_name: str = None) -> str:
        """创建批量任务"""
        batch_id = str(uuid.uuid4())
        with self.lock:
            self.batch_tasks[batch_id] = {
                "batch_id": batch_id,
                "batch_name": batch_name or f"batch_{batch_id[:8]}",
                "task_ids": task_ids,
                "created_at": time.time(),
                "status": "processing",  # processing, completed, failed, partial
            }
        return batch_id

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """获取批量任务状态"""
        with self.lock:
            batch = self.batch_tasks.get(batch_id)
            if not batch:
                return {"status": "not_found", "reason": "批量任务不存在"}

            task_ids = batch["task_ids"]
            completed = 0
            failed = 0
            total = len(task_ids)

            for task_id in task_ids:
                status = task_results.get(task_id, {}).get("status", "not_found")
                if status == "completed":
                    completed += 1
                elif status == "failed":
                    failed += 1

            pending = total - completed - failed

            # 更新批量任务状态
            if pending == 0:
                if failed == 0:
                    batch["status"] = "completed"
                elif completed == 0:
                    batch["status"] = "failed"
                else:
                    batch["status"] = "partial"

            batch["summary"] = {
                "total": total,
                "completed": completed,
                "failed": failed,
                "pending": pending,
                "progress": int((completed / total) * 100) if total > 0 else 0,
            }

            # 获取所有任务的详细状态
            batch["task_statuses"] = {
                task_id: {
                    "status": task_results.get(task_id, {}).get("status", "queued"),
                    "file_path": task_results.get(task_id, {}).get("file_path"),
                    "data": task_results.get(task_id, {}).get("data"),
                }
                for task_id in task_ids
            }

            return batch

    def get_all_batches(self) -> List[Dict]:
        """获取所有批量任务列表"""
        with self.lock:
            return list(self.batch_tasks.values())

    def clean_batch(self, batch_id: str) -> bool:
        """清理批量任务记录"""
        with self.lock:
            if batch_id in self.batch_tasks:
                del self.batch_tasks[batch_id]
                return True
            return False


# 全局批量任务管理器实例
_batch_manager = BatchASRManager()


# --- 重构后的核心处理逻辑 ---


def _process_single_file_core(
    processor: FunASRProcessor,
    audio_path: str,
    output_formats: List[str],
) -> Dict[str, Any]:
    """
    处理单个文件的核心逻辑（不包含队列，由worker调用）。
    这个函数是线程不安全的，必须由单个worker线程串行调用。
    """
    try:
        path_obj = Path(audio_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"文件不存在: {audio_path}")

        output_dir = path_obj.parent
        output_base_name = path_obj.stem

        if output_base_name.endswith(("_video", "_music")):
            output_base_name = "_".join(output_base_name.split("_")[:-1])

        output_suffix = ""
        if path_obj.name.endswith("_video.mp4"):
            output_suffix = "_video"
        elif path_obj.name.endswith("_music.mp3"):
            output_suffix = "_music"

        unique_id = uuid.uuid4()
        output_base_path = str(output_dir / (output_base_name + output_suffix))

        is_video = path_obj.suffix.lower() == ".mp4"
        temp_audio_path = None

        try:
            if is_video:
                temp_audio_path = str(
                    path_obj.with_suffix(f"._temp_audio_{unique_id}.wav")
                )
                if not processor.extract_audio_from_video(
                    str(path_obj), temp_audio_path
                ):
                    raise RuntimeError("从视频提取音频失败")
                audio_to_process = temp_audio_path
            else:
                audio_to_process = str(path_obj)

            audio_data, sample_rate = librosa.load(
                audio_to_process, sr=16000, mono=True
            )

            if len(audio_data) < 100:
                logger.warning(
                    f"[ASR Core] 音频数据太短或无效: {len(audio_data)} 采样点"
                )
                return {"success": False, "reason": "音频数据太短或无效"}

            if processor._model is None and not processor._load_model():
                raise RuntimeError("ASR模型加载失败")

            temp_wav_path = str(
                path_obj.with_suffix(f"._temp_processed_{unique_id}.wav")
            )
            try:
                sf.write(temp_wav_path, audio_data, sample_rate)

                try:
                    # 准备生成参数
                    generate_kwargs = {
                        "input": temp_wav_path,
                        "language": "auto",
                        "use_itn": True,
                        "merge_vad": False,
                        "vad_kwargs": {"max_single_segment_time": 6000},
                    }

                    # FunASR-Nano 必须强制 batch_size=1
                    if "Fun-ASR-Nano" in processor.model_name:
                        generate_kwargs["batch_size"] = 1

                    result = processor._model.generate(**generate_kwargs)

                except Exception as e:
                    logger.warning(f"[ASR Core] 第一次尝试失败: {e}，尝试禁用VAD重试")
                    # 重试参数
                    retry_kwargs = {
                        "input": temp_wav_path,
                        "language": "auto",
                        "use_itn": True,
                        "vad": False,
                    }
                    if "Fun-ASR-Nano" in processor.model_name:
                        retry_kwargs["batch_size"] = 1

                    result = processor._model.generate(**retry_kwargs)
            finally:
                if Path(temp_wav_path).exists():
                    Path(temp_wav_path).unlink()

            if result and len(result) > 0 and isinstance(result[0], dict):
                full_text = result[0].get("text", "")
                segments = result[0].get("segments", [])
                transcription_data = {
                    "text": processor.clean_asr_text(full_text),
                    "segments": segments,
                    "language": result[0].get("language", "auto"),
                    "duration": len(audio_data) / sample_rate,
                }
            else:
                transcription_data = {
                    "text": "",
                    "segments": [],
                    "language": "auto",
                    "duration": len(audio_data) / sample_rate,
                }

            saved_files = []
            for format_type in output_formats:
                output_path = f"{output_base_path}.{format_type.lower()}"
                if processor.save_transcription(
                    transcription_data, output_path, format_type
                ):
                    saved_files.append(output_path)

            if not saved_files:
                raise RuntimeError("保存转写结果失败")

            return {
                "success": True,
                "text": transcription_data.get("text", ""),
                "saved_files": saved_files,
            }

        finally:
            if temp_audio_path and Path(temp_audio_path).exists():
                Path(temp_audio_path).unlink()

    except Exception as e:
        logger.error(f"[ASR Core] 处理 {audio_path} 时发生错误: {e}", exc_info=True)
        return {"success": False, "reason": str(e)}

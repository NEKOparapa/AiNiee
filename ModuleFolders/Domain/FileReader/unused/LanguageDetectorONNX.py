# # 辅助函数：Softmax
# import os
# import sys
# import time
#
# import numpy as np
# import onnxruntime
# import rich
# from langcodes import Language
# from transformers import AutoTokenizer, AutoConfig
#
#
# def softmax(x, axis=-1):
#     """计算 softmax"""
#     x_max = np.max(x, axis=axis, keepdims=True)
#     exp_x = np.exp(x - x_max)
#     return exp_x / np.sum(exp_x, axis=axis, keepdims=True)
#
#
# class LanguageDetectorONNX:
#     _instance = None
#     _initialized = False
#
#     def __new__(cls, *args, **kwargs):
#         if cls._instance is None:
#             # rich.print("[[green]INFO[/]] 准备 ONNX 文本语言检测器实例中...")
#             cls._instance = super().__new__(cls)
#         return cls._instance
#
#     def __init__(self):
#         if self._initialized:
#             return
#
#         rich.print("[[green]INFO[/]] 正在初始化 ONNX 文本语言检测器实例...")
#         # Record start time
#         start_time = time.time()
#         # 设置模型目录
#         script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
#         model_path = os.path.join(script_dir, "Resource", "Models", "language_detection-ONNX")
#
#         self.onnx_model_path = os.path.join(model_path, "onnx", "model_int8.onnx")
#         self.tokenizer_path = model_path
#         self.ort_session = None
#         self.tokenizer = None
#         self.id2label = None
#
#         # 使用 GPU加速 (如果可用)
#         available_providers = onnxruntime.get_available_providers()
#         providers_to_use = ['CPUExecutionProvider']  # 默认
#         if 'DmlExecutionProvider' in available_providers:
#             rich.print("[[green]INFO[/]] 检测到有效加速环境，优先使用GPU进行 ONNX 文本语言检测推理!")
#             providers_to_use.insert(0, 'DmlExecutionProvider')
#         else:
#             rich.print("[[green]INFO[/]] 未检测到有效加速环境，默认使用CPU进行 ONNX 文本语言检测推理!")
#
#         try:
#             self.ort_session = onnxruntime.InferenceSession(self.onnx_model_path, providers=providers_to_use)
#             # rich.print(f"[[green]INFO[/]] ONNX session loaded from {self.onnx_model_path}")
#
#             self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_path)
#             # rich.print(f"[[green]INFO[/]] Tokenizer loaded from {self.tokenizer_path}")
#
#             try:
#                 config = AutoConfig.from_pretrained(model_path)
#                 self.id2label = {int(k): v for k, v in config.id2label.items()}
#                 # rich.print(f"[[green]INFO[/]] Loaded id2label map from config: {model_path}")
#             except Exception as e:
#                 raise ValueError(
#                     f"Could not load id2label from config '{model_path}': {e}. Please provide id2label_map directly."
#                 )
#
#             if not self.id2label or not isinstance(self.id2label, dict):
#                 raise TypeError("Failed to obtain a valid id2label dictionary.")
#
#             self._initialized = True
#             # 计算加载时间（毫秒）
#             load_time_ms = (time.time() - start_time) * 1000
#             rich.print(f"[[green]INFO[/]] ONNX 文本语言检测器已加载! ({load_time_ms:.2f} ms)")
#
#         except Exception as e:
#             rich.print(f"[[red]ERROR[/]] 加载 ONNX 语言检测器失败: {e}")
#             # 清理，防止处于部分初始化状态
#             self._instance = None  # 确保 instance 也被重置
#             self._initialized = False
#             raise
#
#     @classmethod
#     def release(cls):
#         """
#         释放单例持有的资源并重置其状态。
#         允许后续调用重新初始化单例。
#         """
#         if cls._instance:
#             # rich.print("[[green]INFO[/]] 正在释放 ONNX 文本语言检测器...")
#             if cls._instance.ort_session:
#                 # ONNX Runtime sessions don't have an explicit close/del method in Python API
#                 # that guarantees immediate resource release beyond what GC does.
#                 # Setting to None removes our reference, allowing GC to collect it.
#                 cls._instance.ort_session = None
#                 rich.print("[[green]INFO[/]] ONNX 文本语言检测器已释放!")
#             cls._instance.tokenizer = None
#             cls._instance.id2label = None
#             # 其他需要清理的实例变量也可以在这里设置为 None
#
#             # 最重要的是重置类级别的状态变量
#             cls._instance = None
#             cls._initialized = False
#             # rich.print("[[green]INFO[/]] ONNX 文本语言检测器实例已释放并重置!")
#         else:
#             rich.print("[[green]INFO[/]] No LanguageDetectorONNX singleton instance to release.")
#
#     def predict(self, text):
#         """单文本预测方法"""
#         if not self._initialized or not self.ort_session or not self.tokenizer:
#             if not LanguageDetectorONNX._instance or not LanguageDetectorONNX._initialized:
#                 raise RuntimeError("LanguageDetectorONNX singleton is not properly initialized or has been released.")
#             if not self.ort_session or not self.tokenizer:
#                 raise RuntimeError("LanguageDetectorONNX resources (session/tokenizer) are missing. Was it released?")
#         try:
#             # 调用批处理版本，批大小为1
#             results = self.predict_batch([text])
#             return results[0] if results else None  # predict_batch返回列表，取第一个
#         except Exception as e:
#             print(f"Error during single prediction for text '{text[:50]}...': {e}")
#             return None
#
#     def predict_batch(self, texts: list):  # 新增的批处理预测方法
#         """
#         使用加载的 ONNX 模型批量预测输入文本列表的语言。
#
#         Args:
#             texts (list of str): 需要检测语言的文本列表。
#
#         Returns:
#             list of dict: 每个字典包含对应文本的预测结果:
#                           {'label': str, 'confidence': float, 'top_3_scores': list}
#                           如果某一项预测失败，则对应位置可能为 None 或错误信息字典。
#             None: 如果在批处理过程中发生严重错误。
#         """
#         if not self._initialized or not self.ort_session or not self.tokenizer:
#             # 检查 _instance 是否还存在，如果 release 后实例被设为 None，直接访问 self 上的属性会出错
#             # 但由于 __new__ 会返回已存在的 _instance，这里的 self 应该是有效的，只是其内部状态可能被清空
#             if not LanguageDetectorONNX._instance or not LanguageDetectorONNX._initialized:
#                 raise RuntimeError("LanguageDetectorONNX singleton is not properly initialized or has been released.")
#             # 如果 self.ort_session 是 None 但 _initialized 仍然是 True，说明可能是在 release 过程中
#             # 这里更严格的检查是基于 _initialized
#             if not self.ort_session or not self.tokenizer:
#                 raise RuntimeError("LanguageDetectorONNX resources (session/tokenizer) are missing. Was it released?")
#
#         if not texts:
#             return []
#
#         try:
#             # 1. 预处理输入文本 (批处理)
#             # Tokenizer 会自动处理列表输入，并进行填充 (padding) 以使批次内所有序列长度一致
#             inputs = self.tokenizer(texts, return_tensors="np",
#                                     padding=True,  # 关键：开启填充
#                                     truncation=True,
#                                     max_length=512)  # 根据模型调整 max_length
#
#             # 2. 准备 ONNX Runtime 输入 (确保 int64 类型)
#             ort_inputs = {
#                 'input_ids': inputs['input_ids'].astype(np.int64),
#                 'attention_mask': inputs['attention_mask'].astype(np.int64)
#             }
#             if 'token_type_ids' in inputs:  # 确保 token_type_ids (如果模型需要)
#                 ort_inputs['token_type_ids'] = inputs['token_type_ids'].astype(np.int64)
#
#             # 3. 运行推理 (批处理)
#             # ort_outputs[0] 的形状现在是 [batch_size, num_classes]
#             ort_outputs = self.ort_session.run(None, ort_inputs)
#             batch_logits = ort_outputs[0]  # [batch_size, num_classes]
#
#             results_list = []
#             for i in range(batch_logits.shape[0]):  # 遍历批次中的每个结果
#                 logits = batch_logits[i]  # 当前文本的 logits [num_classes]
#
#                 # 4. 后处理 - 计算概率 (置信度)
#                 probabilities = softmax(logits)  # softmax 在最后一个维度上操作
#                 # 先计算argmax获取最高预测结果
#                 predicted_class_id = np.argmax(probabilities)
#                 predicted_label = self.id2label.get(predicted_class_id, "Unknown")
#                 confidence_score = float(probabilities[predicted_class_id])
#
#                 # 创建临时字典，合并yue和zh
#                 temp_scores = {}
#                 for j, prob in enumerate(probabilities):
#                     lang_code = self.id2label.get(j, f"ID_{j}")
#                     lang_name = Language.get(lang_code).language
#
#                     # 将yue统一标记为zh
#                     if lang_name == 'yue':
#                         lang_name = 'zh'
#
#                     # 如果zh或yue已存在，保留概率较高的值
#                     if lang_name in temp_scores:
#                         temp_scores[lang_name] = max(temp_scores[lang_name], float(prob))
#                     else:
#                         temp_scores[lang_name] = float(prob)
#
#                 # 排序并过滤
#                 sorted_scores = sorted(temp_scores.items(), key=lambda item: item[1], reverse=True)
#                 top_scores = [item for item in sorted_scores if item[1] > 0.0002][:5]
#
#                 # 如果预测标签是yue，也转换为zh
#                 if Language.get(predicted_label).language == 'yue':
#                     predicted_label = 'zh'
#                 else:
#                     predicted_label = Language.get(predicted_label).language
#
#                 results_list.append((i, predicted_label, confidence_score, top_scores))
#
#             # 如果你修改了 predict 方法返回元组，这里也需要对应修改
#             # return [(res['label'], res['confidence'], res['top_3_scores']) for res in results_list]
#             return results_list
#
#         except Exception as e:
#             print(f"Error during batch prediction for {len(texts)} texts. First text: '{texts[0][:50]}...': {e}")
#             import traceback
#             traceback.print_exc()
#             # 对于批处理错误，你可能想返回一个列表，其中每个失败的项都是 None 或错误标记
#             return [None] * len(texts)  # 或者更复杂的错误处理

from __future__ import annotations
import json, os, random, sys, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QPoint, QThread, QTimer, Qt, Signal, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (QApplication,QCheckBox,QComboBox,QDialog,QDialogButtonBox,
 QFileDialog,QDoubleSpinBox,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,
 QMainWindow,QMenu,QMessageBox,QPushButton,QSpinBox,QSystemTrayIcon,QTabWidget,
 QTextEdit,QVBoxLayout,QWidget,QInputDialog)
from model_catalog import ModelCatalogError, OPENAI_BASES, discover_models

APP_NAME="Python Desktop Pet v4"; ROOT=Path(__file__).resolve().parent; ASSETS=ROOT/"assets"; CUSTOM=ROOT/"custom_characters"; CONFIG=ROOT/"pet_config.json"; CANVAS=(1536,1024); MAX_EXTRA=4
BUILTINS={"藍色大肥魚（DeepSeek）":"sprite.png","GPT 龍娘":"sprite-gpt.png","大小姐 Claude":"sprite-claude.png","北美貓娘 Gemini":"sprite-gemini.png"}
EXPR={"GPT 龍娘":"gpt","大小姐 Claude":"claude","北美貓娘 Gemini":"gemini"}
DARK_EXPRESSIONS={"default":"sprite-deepseek-dark.png","dark_anger":"sprite-deepseek-dark-anger.png","dark_smirk":"sprite-deepseek-dark-smirk.png","dark_glow":"sprite-deepseek-dark-glow.png","dark_void":"sprite-deepseek-dark-void.png"}
LIGHT_QSS="""QDialog,QWidget{background:#f8fafc;color:#1f2937;} QLabel{color:#334155;} QLineEdit,QTextEdit,QComboBox,QSpinBox,QDoubleSpinBox{background:#ffffff;color:#1f2937;border:1px solid #cbd5e1;border-radius:9px;padding:7px;} QPushButton{background:#2563eb;color:white;border:0;border-radius:9px;padding:8px 14px;} QPushButton:hover{background:#3b82f6;} QPushButton:checked{background:#dc2626;} QTabBar::tab{background:#e2e8f0;color:#334155;padding:9px 16px;border-radius:7px;margin:2px;} QTabBar::tab:selected{background:#2563eb;color:white;} QListWidget{background:#ffffff;border:1px solid #cbd5e1;border-radius:9px;color:#1f2937;}"""
DARK_QSS="""QDialog,QWidget{background:#111827;color:#e5e7eb;} QLabel{color:#dbeafe;} QLineEdit,QTextEdit,QComboBox,QSpinBox,QDoubleSpinBox{background:#1f2937;color:#f9fafb;border:1px solid #374151;border-radius:9px;padding:7px;} QPushButton{background:#2563eb;color:white;border:0;border-radius:9px;padding:8px 14px;} QPushButton:hover{background:#3b82f6;} QPushButton:checked{background:#dc2626;} QTabBar::tab{background:#1f2937;color:#cbd5e1;padding:9px 16px;border-radius:7px;margin:2px;} QTabBar::tab:selected{background:#2563eb;color:white;} QListWidget{background:#0f172a;border:1px solid #374151;border-radius:9px;color:#e5e7eb;}"""
MODERN_QSS=LIGHT_QSS
LINES=["今天也要記得休息一下。","我有看到你在努力喔。","要不要餵我一點飯？","目前沒有啟用 AI 對話，我先用隨機文句陪你。","桌面巡邏完成，暫時安全。","今天的狀態：可愛但有點餓。","別忘了喝水。","我會在這裡陪著你。"]

def configure_tls():
 try:
  import certifi
  ca=certifi.where(); os.environ.setdefault("SSL_CERT_FILE",ca); os.environ.setdefault("REQUESTS_CA_BUNDLE",ca)
 except Exception: pass

def fit_canvas(src:Path,dst:Path):
 with Image.open(src).convert("RGBA") as im:
  im.thumbnail(CANVAS,Image.Resampling.LANCZOS); out=Image.new("RGBA",CANVAS,(0,0,0,0)); out.alpha_composite(im,((CANVAS[0]-im.width)//2,(CANVAS[1]-im.height)//2)); dst.parent.mkdir(parents=True,exist_ok=True); out.save(dst,"PNG")
def cfg_default(): return {"opacity":100,"size":520,"always_on_top":True,"click_through":False,"auto_snap":True,"auto_feed":True,"interval":30,"mode":"simulation","simulation_enabled":True,"simulation_interval":30,"sim_balance":50.0,"debit_min":.01,"debit_max":.10,"credit_min":1.0,"credit_max":5.0,"api_keys":{},"api_profiles":default_profiles(),"active_profile":0,"provider":"DeepSeek","ai_chat_enabled":False,"deepseek_dark":False,"short_memory_limit":20,"short_memory":[],"long_memory":[],"voice_input_mode":"traditional","voice_auto_send":True,"stt_model":"whisper-1","tts_mode":"off","tts_model":"openai/tts-1","tts_voice":"alloy","gemini_live_model":"gemini-3.8-live","gemini_live_voice":"Kore","theme":"light","dynamic_effects":True,"pet_profiles":{},"character":str(ASSETS/"sprite.png"),"expression":"default","event_log":[]}

PROVIDERS=["DeepSeek","OpenAI","Google Gemini","Anthropic","Mistral","xAI / Grok","z.ai","GLM","Ollama","Ollama Cloud","OpenRouter","Cloudflare AI","Groq","Hugging Face","Kiwi","OpenCode","OpenAI 相容自訂端點"]

def default_profiles():
 return [{"name":"DeepSeek 預設","provider":"DeepSeek","key":"","endpoint":"https://api.deepseek.com","model":"deepseek-chat"}]

def migrate_profiles(config):
 if config.get("api_profiles") is not None: return config["api_profiles"]
 profiles=[]
 for provider,key in config.get("api_keys",{}).items(): profiles.append({"name":provider+" 預設","provider":provider,"key":key,"endpoint":"","model":""})
 return profiles or default_profiles()

PREFIX={"DeepSeek":"deepseek/","Google Gemini":"gemini/","Anthropic":"anthropic/","Mistral":"mistral/","xAI / Grok":"xai/","Groq":"groq/","OpenRouter":"openrouter/","Ollama":"ollama/","Ollama Cloud":"ollama_chat/","Cloudflare AI":"cloudflare/","Hugging Face":"huggingface/","z.ai":"openai/","GLM":"openai/","OpenAI 相容自訂端點":"openai/"}
def litellm_model(provider,model,endpoint):
 prefix=PREFIX.get(provider,"")
 if not prefix or not model: return model
 if provider in ("Ollama","Ollama Cloud") and model.startswith(("ollama/","ollama_chat/")): return model
 return model if model.startswith(prefix) else prefix+model

def api_request(provider,key,_chat=None):
 if not key: raise RuntimeError("缺少 API Key")
 if provider=="DeepSeek":
  req=urllib.request.Request("https://api.deepseek.com/user/balance",headers={"Accept":"application/json","Authorization":"Bearer "+key})
  try:
   with urllib.request.urlopen(req,timeout=20) as r: data=json.loads(r.read().decode("utf-8"))
  except urllib.error.HTTPError as e: raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}") from e
  infos=data.get("balance_infos") or []
  balance="、".join(f"{x.get('total_balance')} {x.get('currency','')}" for x in infos) or str(data.get("is_available"))
  return {"balance":balance,"source":"DeepSeek /user/balance"}
 raise RuntimeError(provider+" 目前尚未支援餘額查詢（僅支援 DeepSeek）")

def chat_request(profile,prompt):
 try: from litellm import completion
 except ImportError as e: raise RuntimeError("尚未安裝 LiteLLM，請重新執行 pip install -r requirements.txt") from e
 provider=profile.get("provider","DeepSeek"); key=profile.get("key",""); endpoint=profile.get("endpoint","").strip(); model=profile.get("model","")
 defaults={"DeepSeek":"deepseek/deepseek-chat","OpenAI":"gpt-4o-mini","Google Gemini":"gemini/gemini-2.5-flash","Anthropic":"anthropic/claude-3-5-haiku-latest","Mistral":"mistral/mistral-small-latest","xAI / Grok":"xai/grok-3-mini","Ollama":"ollama/llama3.2","Ollama Cloud":"ollama_chat/llama3.2","OpenRouter":"openrouter/auto","Cloudflare AI":"cloudflare/@cf/meta/llama-3.1-8b-instruct","Groq":"groq/llama-3.3-70b-versatile","Hugging Face":"huggingface/meta-llama/Llama-3.1-8B-Instruct"}
 model=model or defaults.get(provider,"")
 if provider in ("z.ai","GLM") and not endpoint: endpoint=OPENAI_BASES.get(provider,"")
 if provider in ("Ollama","Ollama Cloud") and endpoint.rstrip("/").endswith("/v1"): endpoint=endpoint.rstrip("/")[:-3]
 model=litellm_model(provider,model,endpoint)
 if not model: raise RuntimeError(provider+" 沒有預設模型，請在 API 設定檔填入 LiteLLM model prefix，例如 openrouter/...")
 kwargs={"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":160}
 if key: kwargs["api_key"]=key
 if endpoint: kwargs["api_base"]=endpoint
 response=completion(**kwargs)
 return {"message":response.choices[0].message.content,"raw":response}

VOICE_DIR=ROOT/"voice_cache"; VOSK_MODEL=ROOT/"models"/"vosk-model-small-cn-0.22"

class VoiceRecorder(QThread):
 finished=Signal(str); partial=Signal(str); level=Signal(int); failed=Signal(str)
 def __init__(self,traditional=False,parent=None): super().__init__(parent); self.traditional=traditional; self.stop_event=__import__('threading').Event(); self.frames=[]
 def run(self):
  try:
   import sounddevice as sd, soundfile as sf, numpy as np, time
   recognizer=None; _json=None
   if self.traditional and VOSK_MODEL.exists():
    import json as _json, vosk; recognizer=vosk.KaldiRecognizer(vosk.Model(str(VOSK_MODEL)),16000)
   VOICE_DIR.mkdir(exist_ok=True); path=VOICE_DIR/("recording_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".wav")
   def callback(indata,frames,time,status):
    if status: pass
    self.frames.append(indata.copy()); self.level.emit(min(100,int(float(np.abs(indata).mean())*900)))
    if recognizer:
     recognizer.AcceptWaveform((indata[:,0]*32767).astype(np.int16).tobytes()); partial=_json.loads(recognizer.PartialResult()).get("partial","")
     if partial: self.partial.emit(partial)
   started=time.monotonic()
   with sd.InputStream(samplerate=16000,channels=1,dtype="float32",callback=callback):
    while not self.stop_event.wait(.05):
     if time.monotonic()-started>=120: break
   sf.write(str(path),np.concatenate(self.frames,axis=0) if self.frames else np.zeros((1,1),dtype="float32"),16000,subtype="PCM_16"); self.finished.emit(str(path))
  except Exception as e:self.failed.emit(str(e))
 def stop(self): self.stop_event.set()

class VoiceTranscriber(QThread):
 finished=Signal(bool,str)
 def __init__(self,path,mode,profile,parent=None): super().__init__(parent); self.path=path; self.mode=mode; self.profile=profile
 def run(self):
  try:
   if self.mode=="traditional":
    if not VOSK_MODEL.exists(): raise RuntimeError("找不到本機 Vosk 中文模型，請先執行 download_voice_model.bat")
    import json as _json, wave, vosk
    model=vosk.Model(str(VOSK_MODEL)); wf=wave.open(self.path,"rb"); rec=vosk.KaldiRecognizer(model,wf.getframerate())
    while True:
     data=wf.readframes(4000)
     if not data: break
     rec.AcceptWaveform(data)
    text=_json.loads(rec.FinalResult()).get("text","")
   else:
    from litellm import transcription
    with open(self.path,"rb") as f: result=transcription(model=self.profile.get("stt_model") or "whisper-1",file=f,api_key=self.profile.get("key") or None,api_base=self.profile.get("endpoint") or None)
    text=getattr(result,"text","") or (result.get("text","") if isinstance(result,dict) else "")
   self.finished.emit(True,text.strip())
  except Exception as e:self.finished.emit(False,str(e))

class TTSWorker(QThread):
 finished=Signal(bool,str)
 def __init__(self,text,mode,profile,parent=None): super().__init__(parent); self.text=text; self.mode=mode; self.profile=profile
 def run(self):
  try:
   if self.mode=="traditional":
    import pyttsx3; engine=pyttsx3.init(); engine.say(self.text); engine.runAndWait(); self.finished.emit(True,"")
   else:
    from litellm import speech
    VOICE_DIR.mkdir(exist_ok=True); path=VOICE_DIR/("tts_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".mp3"); result=speech(model=self.profile.get("tts_model") or "openai/tts-1",voice=self.profile.get("voice") or "alloy",input=self.text,api_key=self.profile.get("key") or None,api_base=self.profile.get("endpoint") or None); result.stream_to_file(path); self.finished.emit(True,str(path))
  except Exception as e:self.finished.emit(False,str(e))

class GeminiLiveWorker(QThread):
 finished=Signal(bool,dict)
 def __init__(self,path,profile,system_instruction="",model="gemini-3.8-live",voice="Kore",parent=None): super().__init__(parent); self.path=path; self.profile=profile; self.system_instruction=system_instruction; self.model=model; self.voice=voice; self.cancel_event=__import__('threading').Event(); self.timeout_seconds=180
 def run(self):
  try:
   import asyncio
   key=self.profile.get("key")
   if not key: raise RuntimeError("純語音需要目前 Google Gemini 設定檔的 API Key")
   result=asyncio.run(self.session_with_timeout(key))
   if self.cancel_event.is_set(): self.finished.emit(False,{"cancelled":True,"error":"使用者中斷 Gemini Live"}); return
   self.finished.emit(True,result)
  except asyncio.TimeoutError:self.finished.emit(False,{"timeout":True,"error":"Gemini Live 等待逾時"})
  except asyncio.CancelledError:self.finished.emit(False,{"cancelled":True,"error":"Gemini Live 已取消"})
  except Exception as e:self.finished.emit(False,{"error":str(e)})
 def cancel(self): self.cancel_event.set()
 async def session_with_timeout(self,key):
  import asyncio
  return await asyncio.wait_for(self.session(key),timeout=self.timeout_seconds)
 async def session(self,key):
  import asyncio, wave
  from google import genai
  from google.genai import types
  client=genai.Client(api_key=key); pcm=[]; transcript=[]; user_text=[]; model_text=[]
  with wave.open(self.path,"rb") as wf:
   rate=wf.getframerate()
   live_config={"response_modalities":["AUDIO"],"input_audio_transcription":{},"output_audio_transcription":{},"speech_config":{"voice_config":{"prebuilt_voice_config":{"voice_name":self.voice}}}}
   if self.system_instruction.strip(): live_config["system_instruction"]=self.system_instruction
   async with client.aio.live.connect(model=self.model,config=live_config) as session:
    while True:
     if self.cancel_event.is_set(): return {"audio":None,"text":"","cancelled":True}
     chunk=wf.readframes(2048)
     if not chunk: break
     await session.send_realtime_input(audio=types.Blob(data=chunk,mime_type=f"audio/pcm;rate={rate}"))
    await session.send_realtime_input(audio_stream_end=True)
    receiver=session.receive()
    import time
    deadline=time.monotonic()+self.timeout_seconds
    pending=None; done_turn=False
    try:
     while time.monotonic()<deadline and not self.cancel_event.is_set() and not done_turn:
      if pending is None: pending=asyncio.ensure_future(receiver.__anext__())
      finished,_=await asyncio.wait({pending},timeout=1.0)
      if not finished: continue
      task=pending; pending=None
      try: response=task.result()
      except StopAsyncIteration: break
      content=getattr(response,"server_content",None)
      if content:
       inp=getattr(content,"input_transcription",None); out=getattr(content,"output_transcription",None)
       if inp and getattr(inp,"text",None): user_text.append(inp.text)
       if out and getattr(out,"text",None): model_text.append(out.text)
       turn=getattr(content,"model_turn",None)
       if turn:
        for part in getattr(turn,"parts",[]) or []:
         inline=getattr(part,"inline_data",None)
         if inline and getattr(inline,"data",None): pcm.append(inline.data)
       if getattr(content,"turn_complete",False): done_turn=True
    finally:
     if pending is not None: pending.cancel()
  if user_text: transcript.append("使用者："+"".join(user_text).strip())
  if model_text: transcript.append("Gemini："+"".join(model_text).strip())
  if self.cancel_event.is_set(): return {"audio":None,"text":"","cancelled":True}
  out_path=None
  if pcm:
   VOICE_DIR.mkdir(exist_ok=True)
   out_path=VOICE_DIR/("gemini_live_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".wav")
   with wave.open(str(out_path),"wb") as out:
    out.setnchannels(1); out.setsampwidth(2); out.setframerate(24000); out.writeframes(b"".join(pcm))
  return {"audio":str(out_path) if out_path else None,"text":"\n".join(transcript)}

class Worker(QThread):
 done=Signal(bool,dict)
 def __init__(self,provider_or_profile,key_or_chat=None,chat=None,parent=None):
  super().__init__(parent); self.legacy=not isinstance(provider_or_profile,dict)
  if self.legacy: self.provider=provider_or_profile; self.key=key_or_chat; self.chat=chat; self.profile={"provider":self.provider,"key":self.key}
  else: self.profile=provider_or_profile; self.chat=key_or_chat
 def run(self):
  try:
   data=api_request(self.provider,self.key,self.chat) if self.legacy else chat_request(self.profile,self.chat)
   self.done.emit(True,data)
  except Exception as e:self.done.emit(False,{"error":str(e)})

class ModelListWorker(QThread):
 models_ready=Signal(bool,list,str)
 def __init__(self,profile,parent=None): super().__init__(parent); self.profile=dict(profile)
 def run(self):
  try:
   models,source,note=discover_models(self.profile); self.models_ready.emit(True,models,note or source)
  except ModelCatalogError as e:self.models_ready.emit(False,[],str(e))
  except Exception as e:self.models_ready.emit(False,[],str(e))

class SpeechBubble(QLabel):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setWordWrap(True); self.setAlignment(Qt.AlignCenter); self.setAttribute(Qt.WA_TransparentForMouseEvents); self.hide()
 def show_message(self,text,thought=False):
  dark=self.pet.is_deepseek_dark(); self._thought=thought; self.setText(text);
  if dark:
   self.setStyleSheet("QLabel{color:#ffe8ed;background:%s;border:2px solid #b51f3a;border-radius:16px;padding:8px 12px;font-size:15px;font-weight:bold;}" % ("#211017" if thought else "#35111b")); (QTimer.singleShot(180,self.dark_flash) if self.pet.config.get("dynamic_effects",True) else None)
  else:self.setStyleSheet("QLabel{color:#222;background:%s;border:2px solid #555;border-radius:16px;padding:8px 12px;font-size:15px;}" % ("#e8e8e8" if thought else "#fffdf2"))
  self.setMaximumWidth(max(180,min(360,self.pet.width()-20))); self.adjustSize(); self.resize(min(360,max(180,self.sizeHint().width())),max(44,self.sizeHint().height())); self.move(max(5,(self.pet.width()-self.width())//2),8); self.raise_(); self.show(); QTimer.singleShot(6500,self.hide)
 def dark_flash(self):
  if self.isVisible() and self.pet.is_deepseek_dark(): self.setStyleSheet("QLabel{color:#fff;background:#5b1020;border:3px solid #ff3658;border-radius:16px;padding:7px 11px;font-size:15px;font-weight:bold;}"); QTimer.singleShot(240,self.restore_dark)
 def restore_dark(self):
  if self.isVisible() and self.pet.is_deepseek_dark(): self.setStyleSheet("QLabel{color:#ffe8ed;background:%s;border:2px solid #b51f3a;border-radius:16px;padding:8px 12px;font-size:15px;font-weight:bold;}" % ("#211017" if getattr(self,"_thought",False) else "#35111b"))

class VoiceSettingsDialog(QDialog):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setStyleSheet(DARK_QSS if pet.config.get("theme","light")=="dark" else LIGHT_QSS); self.setWindowTitle("語音與 TTS 設定"); self.resize(560,360); f=QFormLayout(self); self.input_mode=QComboBox(); self.input_mode.addItems(["traditional","ai"]); self.input_mode.setCurrentText(pet.config.get("voice_input_mode","traditional")); f.addRow("語音輸入模式",self.input_mode); self.auto_send=QCheckBox("辨識完成後自動送出"); self.auto_send.setChecked(pet.config.get("voice_auto_send",True)); f.addRow(self.auto_send); self.stt=QLineEdit(pet.config.get("stt_model","whisper-1")); f.addRow("AI 語音模型",self.stt); self.tts=QComboBox(); self.tts.addItems(["off","traditional","ai"]); self.tts.setCurrentText(pet.config.get("tts_mode","off")); f.addRow("文字轉聲音模式",self.tts); self.tts_model=QLineEdit(pet.config.get("tts_model","openai/tts-1")); f.addRow("AI TTS 模型",self.tts_model); self.voice=QLineEdit(pet.config.get("tts_voice","alloy")); f.addRow("AI 聲音",self.voice); self.live_model=QLineEdit(pet.config.get("gemini_live_model","gemini-3.8-live")); f.addRow("Gemini Live 模型",self.live_model); self.live_voice=QLineEdit(pet.config.get("gemini_live_voice","Kore")); f.addRow("Gemini Live 聲音",self.live_voice); self.anim=QCheckBox("啟用語音錄音／回覆動態效果"); self.anim.setChecked(pet.config.get("dynamic_effects",True)); f.addRow(self.anim); note=QLabel("traditional 需要 models\\vosk-model-small-cn-0.22；ai 會使用目前選定 API 設定檔的 Key 與端點。AI TTS 也需要支援 speech 的模型；純語音會使用目前 Google Gemini 設定檔並透過 Gemini Live WebSocket 串流。"); note.setWordWrap(True); f.addRow(note); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.save); b.rejected.connect(self.reject); f.addRow(b)
 def save(self):
  self.pet.update({"voice_input_mode":self.input_mode.currentText(),"voice_auto_send":self.auto_send.isChecked(),"stt_model":self.stt.text().strip(),"tts_mode":self.tts.currentText(),"tts_model":self.tts_model.text().strip(),"tts_voice":self.voice.text().strip(),"gemini_live_model":self.live_model.text().strip(),"gemini_live_voice":self.live_voice.text().strip(),"dynamic_effects":self.anim.isChecked()}); self.accept()

class PetSettingsDialog(QDialog):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setStyleSheet(DARK_QSS if pet.config.get("theme","light")=="dark" else LIGHT_QSS); self.setWindowTitle("目前寵物設定"); self.resize(420,250); f=QFormLayout(self); self.opacity=QSpinBox(); self.opacity.setRange(20,100); self.opacity.setValue(int(pet.config.get("opacity",100))); f.addRow("透明度 %",self.opacity); self.size=QSpinBox(); self.size.setRange(180,1000); self.size.setValue(int(pet.config.get("size",520))); f.addRow("大小寬度 px（比例固定）",self.size); self.snap=QCheckBox("自動貼邊"); self.snap.setChecked(pet.config.get("auto_snap",True)); f.addRow(self.snap); self.dynamic=QCheckBox("啟用動畫／動態效果"); self.dynamic.setChecked(pet.config.get("dynamic_effects",True)); f.addRow(self.dynamic); key=QLabel("設定檔："+pet.current.name); f.addRow(key); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.save); b.rejected.connect(self.reject); f.addRow(b)
 def save(self):
  values={"opacity":self.opacity.value(),"size":self.size.value(),"auto_snap":self.snap.isChecked(),"dynamic_effects":self.dynamic.isChecked()}; self.pet.save_pet_profile(values); self.pet.update(values); self.accept()

class MemoryDialog(QDialog):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setStyleSheet(DARK_QSS if pet.config.get("theme","light")=="dark" else LIGHT_QSS); self.setWindowTitle("角色記憶管理"); self.resize(560,420); root=QVBoxLayout(self); root.addWidget(QLabel("長期記憶（每行一條，會持續提供給 AI）")); self.long=QTextEdit(); self.long.setPlainText("\n".join(pet.config.get("long_memory",[]))); self.long.setPlaceholderText("例如：\n主人喜歡喝熱茶。\n角色名字是小藍。\n不要忘記上次約定的事情。"); root.addWidget(self.long); form=QFormLayout(); self.limit=QSpinBox(); self.limit.setRange(1,100); self.limit.setValue(int(pet.config.get("short_memory_limit",20))); form.addRow("短期記憶對話次數",self.limit); root.addLayout(form); clear=QPushButton("清除短期記憶"); clear.clicked.connect(self.clear_short); root.addWidget(clear); note=QLabel("短期記憶預設保留最近 20 次完整對話（最多 40 則 user/assistant 訊息）；長期記憶不會自動淘汰。"); note.setWordWrap(True); root.addWidget(note); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.save); b.rejected.connect(self.reject); root.addWidget(b)
 def clear_short(self): self.pet.update({"short_memory":[]})
 def save(self):
  self.pet.update({"long_memory":[x.strip() for x in self.long.toPlainText().splitlines() if x.strip()],"short_memory_limit":self.limit.value()}); self.accept()

class ChatDialog(QDialog):
 def __init__(self,pet):
  super().__init__(None,Qt.FramelessWindowHint|Qt.Tool); self.pet=pet; self.setStyleSheet(DARK_QSS if pet.config.get("theme","light")=="dark" else LIGHT_QSS); self.setWindowTitle("角色對話"); self.setMinimumSize(390,330)
  root=QVBoxLayout(self); title=QLabel("角色對話視窗"); title.setStyleSheet("font-weight:bold;font-size:16px;"); root.addWidget(title); self.profile=QComboBox(); self.reload_profiles(); root.addWidget(self.profile); self.history=QTextEdit(); self.history.setReadOnly(True); root.addWidget(self.history); row=QHBoxLayout(); self.input=QLineEdit(); self.input.setPlaceholderText("輸入訊息…"); self.input.returnPressed.connect(self.send); row.addWidget(self.input); self.mic=QPushButton("麥克風"); self.mic.setCheckable(True); self.mic.clicked.connect(lambda:self.pet.toggle_voice(self)); row.addWidget(self.mic); self.pure=QPushButton("純語音"); self.pure.setCheckable(True); self.pure.clicked.connect(lambda:self.pet.toggle_pure_voice(self)); row.addWidget(self.pure); send=QPushButton("送出"); send.clicked.connect(self.send); row.addWidget(send); root.addLayout(row); self.voice_status=QLabel("語音："+self.pet.config.get("voice_input_mode","traditional")); root.addWidget(self.voice_status); note=QLabel("對話視窗只負責聊天、錄音與純語音互動；API 設定、模型列表、記憶與語音細節請從右鍵控制中心管理。長期記憶與最近短期記憶會自動提供給普通對話和 Gemini Live。"); note.setWordWrap(True); root.addWidget(note); close=QPushButton("收起聊天框"); close.clicked.connect(self.close); root.addWidget(close); self.input.setFocus()
 def reload_profiles(self):
  self.profile.clear(); items=self.pet.config.get("api_profiles",default_profiles()); self.profile.addItems([f"{x.get('name','未命名')}｜{x.get('provider','')}｜{x.get('model') or '預設模型'}" for x in items]); self.profile.setCurrentIndex(max(0,min(self.pet.config.get("active_profile",0),len(items)-1)) if items else -1)
 def showEvent(self,e): super().showEvent(e); self.move(self.pet.x()+max(0,(self.pet.width()-self.width())//2),self.pet.y()+max(20,self.pet.height()//3))
 def add_message(self,who,text): self.history.append(f"<b>{who}：</b>{text}")
 def send(self):
  text=self.input.text().strip()
  if text: self.input.clear(); self.pet.handle_chat(text,self,self.profile.currentIndex())
 def sync_settings(self,key,value):
  if key in ("api_profiles","active_profile"):
   selected=max(0,self.profile.currentIndex()); self.reload_profiles(); self.profile.setCurrentIndex(min(selected,self.profile.count()-1) if self.profile.count() else -1)
  if key in ("voice_input_mode","voice_auto_send","gemini_live_model","gemini_live_voice"):
   self.voice_status.setText("語音："+self.pet.config.get("voice_input_mode","traditional"))
  if key=="theme": self.setStyleSheet(DARK_QSS if value=="dark" else LIGHT_QSS)
  if key in ("long_memory","short_memory_limit","short_memory"): self.voice_status.setToolTip("記憶設定已同步；普通對話與 Gemini Live 會使用最新內容。")

class Bowl(QLabel):
 fed=Signal()
 def __init__(self,parent):
  super().__init__(parent); self.host=parent; self.drag=None; self.setText("🍚"); self.setAlignment(Qt.AlignCenter); self.setStyleSheet("font-size:40px;background:rgba(255,255,255,210);border-radius:24px;padding:5px;"); self.resize(78,78)
 def mousePressEvent(self,e):
  if e.button()==Qt.LeftButton:self.drag=e.globalPosition().toPoint()-self.host.mapToGlobal(self.pos()); e.accept()
 def mouseMoveEvent(self,e):
  if self.drag is not None and e.buttons()&Qt.LeftButton:self.move(e.globalPosition().toPoint()-self.host.mapToGlobal(QPoint(0,0))-self.drag)
 def mouseReleaseEvent(self,e):
  self.drag=None
  cx,cy=self.geometry().center().x(),self.geometry().center().y(); x0,x1=self.host.width()//3,2*self.host.width()//3; y0,y1=self.host.height()//5,4*self.host.height()//5
  if x0<=cx<=x1 and y0<=cy<=y1: self.fed.emit()
  else: self.move(max(0,min(self.host.width()-self.width(),self.x())),max(0,min(self.host.height()-self.height(),self.y())))

class Walker(QWidget):
 def __init__(self,paths,index,pet):
  super().__init__(pet); self.pet=pet; self.paths=paths; self.index=index; self.side=1; self.drag=None; self.path=paths["side"]
  self.setWindowFlags(Qt.FramelessWindowHint|Qt.Tool|Qt.WindowStaysOnTopHint); self.setAttribute(Qt.WA_TranslucentBackground)
  self.label=QLabel(self); self.label.setStyleSheet("background:transparent"); self.resize(230,180); self.render_image(); self.ground=None
  self.timer=QTimer(self); self.timer.timeout.connect(self.step); self.timer.start(35)
 def render_image(self):
  self.label.resize(self.size()); p=QPixmap(str(self.path)); self.label.setPixmap(p.scaled(self.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
 def resizeEvent(self,e): self.render_image()
 def showEvent(self,e):
  s=QApplication.primaryScreen().availableGeometry(); self.move(s.left()+30+self.index*250,s.bottom()-self.height()-20)
 def step(self):
  s=QApplication.primaryScreen().availableGeometry(); nx=self.x()+self.side*(2+self.index); left,right=s.left(),s.right()-self.width()
  if nx<=left or nx>=right:
   nx=max(left,min(right,nx)); self.side*=-1; self.path=self.paths["front" if self.side<0 else "back"]; self.render_image(); QTimer.singleShot(300,self.show_side)
  else:
   self.path=self.paths["side"]; self.render_image()
  if self.ground is None: self.ground=s.bottom()-self.height()-20
  self.move(nx,self.y()); self.avoid()
 def show_side(self): self.path=self.paths["side"]; self.render_image()
 def avoid(self):
  if self.geometry().intersects(self.pet.geometry()): self.move(self.x(),self.y()-20)
  elif self.ground is not None and self.drag is None and self.y()<self.ground: self.move(self.x(),min(self.ground,self.y()+8))
  for other in self.pet.walkers:
   if other is not self and self.geometry().intersects(other.geometry()): self.move(self.x(),self.y()-10)
 def mousePressEvent(self,e):
  if e.button()==Qt.LeftButton:self.drag=e.globalPosition().toPoint()-self.frameGeometry().topLeft()
  elif e.button()==Qt.RightButton:self.pet.chat()
 def mouseMoveEvent(self,e):
  if self.drag is not None and e.buttons()&Qt.LeftButton:self.move(e.globalPosition().toPoint()-self.drag)
 def mouseReleaseEvent(self,e): self.drag=None
 def closeEvent(self,e): self.timer.stop(); super().closeEvent(e)

class KeyDialog(QDialog):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setStyleSheet(DARK_QSS if pet.config.get("theme","light")=="dark" else LIGHT_QSS); self.setWindowTitle("API 設定檔管理"); self.resize(760,500); self.items=[dict(x) for x in pet.config.get("api_profiles",default_profiles())]; self.model_worker=None; root=QVBoxLayout(self); row=QHBoxLayout(); self.list=QListWidget(); row.addWidget(self.list,1); form=QFormLayout(); self.name=QLineEdit(); self.provider=QComboBox(); self.provider.addItems(PROVIDERS); self.key=QLineEdit(); self.key.setEchoMode(QLineEdit.Password); self.endpoint=QLineEdit(); self.model=QLineEdit(); self.models=QComboBox(); self.models.setEditable(True); self.models.activated.connect(lambda index:self.model.setText(self.models.itemData(index) or self.models.currentText())); self.refresh_models_button=QPushButton("刷新模型列表"); self.refresh_models_button.clicked.connect(self.refresh_models); self.model_status=QLabel("可手動輸入模型 ID；刷新失敗時仍可保存手動值。"); self.model_status.setWordWrap(True); form.addRow("設定檔名稱",self.name); form.addRow("供應商",self.provider); form.addRow("API Key",self.key); form.addRow("端點 URL",self.endpoint); form.addRow("目前模型（手動可編輯）",self.model); form.addRow("遠端模型列表",self.models); form.addRow("模型操作",self.refresh_models_button); form.addRow(self.model_status); row.addLayout(form,3); root.addLayout(row); buttons=QHBoxLayout(); add=QPushButton("新增設定檔"); add.clicked.connect(self.add); remove=QPushButton("刪除選取"); remove.clicked.connect(self.remove); buttons.addWidget(add); buttons.addWidget(remove); root.addLayout(buttons); note=QLabel("模型查詢順序：供應商專用 API → OpenAI-compatible /models fallback → 手動輸入。Ollama 預設端點為 http://localhost:11434/v1，可不填 Key；自訂端點必須提供 OpenAI-compatible /models 或 /v1/models。"); note.setWordWrap(True); root.addWidget(note); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.save); b.rejected.connect(self.reject); root.addWidget(b); self._row=-1; self.list.currentRowChanged.connect(self.load_item); self.refresh_list(); self.list.setCurrentRow(0)
 def refresh_list(self): self._row=-1; self.list.clear(); self.list.addItems([x.get("name",x.get("provider","未命名")) for x in self.items])
 def load_item(self,row):
  if 0<=self._row<len(self.items) and self._row!=row: self.items[self._row]=self.current()
  self._row=row
  if 0<=row<len(self.items):
   x=self.items[row]; self.name.setText(x.get("name","")); self.provider.setCurrentText(x.get("provider","DeepSeek")); self.key.setText(x.get("key","")); self.endpoint.setText(x.get("endpoint","")); self.model.setText(x.get("model","")); self.models.clear(); self.models.addItem("（尚未刷新；可直接手動輸入）",x.get("model","")); self.model_status.setText("可手動輸入模型 ID；刷新失敗時仍可保存手動值。")
 def current(self): return {"name":self.name.text().strip() or "未命名","provider":self.provider.currentText(),"key":self.key.text().strip(),"endpoint":self.endpoint.text().strip(),"model":self.model.text().strip()}
 def store_current(self):
  row=self.list.currentRow()
  if 0<=row<len(self.items): self.items[row]=self.current()
 def refresh_models(self):
  self.store_current(); profile=self.current(); self.refresh_models_button.setEnabled(False); self.model_status.setText("正在查詢模型列表，不會阻塞主視窗…"); self.model_worker=ModelListWorker(profile,self); self.model_worker.models_ready.connect(self.models_done); self.model_worker.start()
 def models_done(self,ok,models,message):
  self.model_worker=None; self.refresh_models_button.setEnabled(True); self.models.clear()
  if not ok: self.models.addItem("（查詢失敗，手動輸入模型 ID）",self.model.text()); self.model_status.setText(message); return
  for item in models: self.models.addItem(f"{item.get('label',item['id'])}｜{item['id']}",item["id"])
  self.models.setCurrentIndex(next((i for i in range(self.models.count()) if self.models.itemData(i)==self.model.text()),0) if self.models.count() else -1); self.model_status.setText(f"已取得 {len(models)} 個模型；來源：{message}。模型欄仍可手動修改。")
 def add(self): self.store_current(); self.items.append({"name":"新設定檔","provider":"OpenAI","key":"","endpoint":"","model":"gpt-4o-mini"}); self.refresh_list(); self.list.setCurrentRow(len(self.items)-1)
 def remove(self):
  row=self.list.currentRow()
  if 0<=row<len(self.items): self.items.pop(row); self.refresh_list(); self.list.setCurrentRow(max(0,row-1))
 def save(self):
  self.store_current(); self.pet.update({"api_profiles":self.items,"active_profile":max(0,min(int(self.pet.config.get("active_profile",0)),len(self.items)-1)) if self.items else 0}); self.accept()

class SimulationDialog(QDialog):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setWindowTitle("模擬模式控制"); f=QFormLayout(self); self.enabled=QCheckBox("啟用自動事件"); self.enabled.setChecked(pet.config.get("simulation_enabled",True)); f.addRow(self.enabled); self.balance=QDoubleSpinBox(); self.balance.setRange(-1e9,1e9); self.balance.setDecimals(2); self.balance.setValue(float(pet.config.get("sim_balance",50))); f.addRow("餘額",self.balance); self.interval=QSpinBox(); self.interval.setRange(1,86400); self.interval.setValue(int(pet.config.get("simulation_interval",30))); self.interval.setSuffix(" 秒"); f.addRow("事件間隔",self.interval)
  for key,label,lo,hi in [("debit_min","扣款下限",0,9999),("debit_max","扣款上限",0,9999),("credit_min","充值下限",0,9999),("credit_max","充值上限",0,9999)]:
   w=QDoubleSpinBox(); w.setRange(lo,hi); w.setDecimals(2); w.setValue(float(pet.config.get(key,1))); setattr(self,key,w); f.addRow(label,w)
  b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.save); b.rejected.connect(self.reject); f.addRow(b); now=QPushButton("立即模擬事件"); now.clicked.connect(pet.simulate); f.addRow(now)
 def save(self):
  c={"simulation_enabled":self.enabled.isChecked(),"sim_balance":self.balance.value(),"simulation_interval":self.interval.value()}; c.update({k:getattr(self,k).value() for k in ("debit_min","debit_max","credit_min","credit_max")}); self.pet.update(c); self.pet.sim_timer.setInterval(int(self.interval.value()*1000)); self.accept()

class Panel(QDialog):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setStyleSheet(DARK_QSS if pet.config.get("theme","light")=="dark" else LIGHT_QSS); self.setWindowTitle("Python Desktop Pet v4｜控制中心"); self.resize(720,600); root=QVBoxLayout(self); tabs=QTabWidget(); root.addWidget(tabs)
  tab=QWidget(); h=QHBoxLayout(tab); self.list=QListWidget(); self.paths=[]
  for label,name in BUILTINS.items(): self.list.addItem(label); self.paths.append(ASSETS/name)
  self.list.currentRowChanged.connect(self.preview); h.addWidget(self.list); col=QVBoxLayout(); self.pic=QLabel(); self.pic.setMinimumSize(350,250); self.pic.setAlignment(Qt.AlignCenter); col.addWidget(self.pic); use=QPushButton("套用角色"); use.setEnabled(not pet.is_busy()); use.clicked.connect(self.use); col.addWidget(use); imp=QPushButton("匯入自訂角色"); imp.clicked.connect(pet.import_character); col.addWidget(imp); h.addLayout(col); tabs.addTab(tab,"角色與表情"); self.list.setCurrentRow(0)
  exp=QWidget(); ef=QFormLayout(exp); self.expr=QComboBox(); self.expr.addItems(["default","expression_11","expression_12","expression_21","expression_22","dark_anger","dark_smirk","dark_glow","dark_void"]); self.expr.setCurrentText(pet.config.get("expression","default")); ef.addRow("舊表情差分",self.expr); applye=QPushButton("套用表情"); applye.clicked.connect(lambda:pet.set_expression(self.expr.currentText())); ef.addRow(applye); self.expr_note=QLabel("Claude、Gemini、GPT 的舊表情已接入；黑化 DeepSeek 另有 anger／smirk／glow／void 專屬表情；沒有 walking sprite 的角色不會自動行走。"); self.expr_note.setWordWrap(True); ef.addRow(self.expr_note); tabs.addTab(exp,"表情差分")
  ap=QWidget(); af=QFormLayout(ap); self.opacity=QSpinBox(); self.opacity.setRange(20,100); self.opacity.setValue(pet.config.get("opacity",100)); af.addRow("透明度 %",self.opacity); self.size=QSpinBox(); self.size.setRange(180,1000); self.size.setValue(pet.config.get("size",520)); af.addRow("寬度 px",self.size); self.snap=QCheckBox("自動貼邊"); self.snap.setChecked(pet.config.get("auto_snap",True)); af.addRow(self.snap); applya=QPushButton("套用目前寵物外觀"); applya.clicked.connect(self.apply_appearance); af.addRow(applya); profile=QPushButton("開啟目前寵物設定檔"); profile.clicked.connect(lambda:PetSettingsDialog(pet).exec()); af.addRow(profile); tabs.addTab(ap,"外觀與 DPI")
  sim=QWidget(); sf=QVBoxLayout(sim); self.status=QLabel(); self.status.setWordWrap(True); sf.addWidget(self.status); b=QPushButton("模擬模式設定"); b.clicked.connect(lambda:(SimulationDialog(pet).exec(),self.refresh())); sf.addWidget(b); b=QPushButton("立即模擬事件"); b.clicked.connect(lambda:(pet.simulate(),self.refresh())); sf.addWidget(b); self.log=QTextEdit(); self.log.setReadOnly(True); sf.addWidget(self.log); tabs.addTab(sim,"模擬與事件紀錄"); self.refresh()
  api=QWidget(); q=QVBoxLayout(api); self.api_status=QLabel("API 模式會使用目前供應商的實際查詢；DeepSeek 使用官方 /user/balance。"); self.api_status.setWordWrap(True); q.addWidget(self.api_status); k=QPushButton("API Key、模型列表與對話設定"); k.clicked.connect(lambda:KeyDialog(pet).exec()); q.addWidget(k); r=QPushButton("立即查詢 API 餘額"); r.clicked.connect(pet.refresh_api); q.addWidget(r); memory=QPushButton("記憶管理（短期／長期）"); memory.clicked.connect(lambda:MemoryDialog(pet).exec()); q.addWidget(memory); voice=QPushButton("語音與 Gemini Live 設定"); voice.clicked.connect(lambda:VoiceSettingsDialog(pet).exec()); q.addWidget(voice); chat=QPushButton("開啟對話視窗"); chat.clicked.connect(pet.chat); q.addWidget(chat); q.addStretch(); tabs.addTab(api,"API 與對話")
  close=QPushButton("關閉"); close.clicked.connect(self.close); root.addWidget(close)
 def preview(self,row):
  if 0<=row<len(self.paths): self.pic.setPixmap(QPixmap(str(self.paths[row])).scaled(self.pic.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
 def use(self):
  row=self.list.currentRow()
  if 0<=row<len(self.paths): self.pet.select(self.paths[row].name)
 def apply_appearance(self): self.pet.save_pet_profile({"opacity":self.opacity.value(),"size":self.size.value(),"auto_snap":self.snap.isChecked()}); self.pet.update({"opacity":self.opacity.value(),"size":self.size.value(),"auto_snap":self.snap.isChecked()})
 def sync_settings(self,key,value):
  if key=="theme": self.setStyleSheet(DARK_QSS if value=="dark" else LIGHT_QSS)
  if key in ("opacity","size","auto_snap"):
   self.opacity.blockSignals(True); self.opacity.setValue(int(self.pet.config.get("opacity",self.opacity.value()))); self.opacity.blockSignals(False)
   self.size.blockSignals(True); self.size.setValue(int(self.pet.config.get("size",self.size.value()))); self.size.blockSignals(False)
   self.snap.blockSignals(True); self.snap.setChecked(bool(self.pet.config.get("auto_snap",self.snap.isChecked()))); self.snap.blockSignals(False)
   self.refresh()
  elif key in ("sim_balance","last_event","event_log","simulation_enabled","simulation_interval"): self.refresh()
 def refresh(self):
  self.status.setText(f"模式：{self.pet.config.get('mode')}\n模擬餘額：{float(self.pet.config.get('sim_balance',0)):.2f}\n最後事件：{self.pet.config.get('last_event','尚未發生')}"); self.log.setPlainText("\n".join(self.pet.config.get("event_log",[])))

class Pet(QMainWindow):
 settings_changed=Signal(str,object)
 def __init__(self):
  super().__init__(); self.config=self.load(); self.current=Path(self.config.get("character",ASSETS/"sprite.png")); self.load_pet_profile(); self.save(); self.apply_theme(); self.drag=None; self.bowl=None; self.walkers=[]; self.worker=None; self.panel=None; self.label=QLabel(self); self.label.setStyleSheet("background:transparent"); self.setCentralWidget(self.label); self.setWindowTitle(APP_NAME); self.setAttribute(Qt.WA_TranslucentBackground); self.apply(); self.tray=QSystemTrayIcon(self); self.tray.setIcon(QIcon(str(ASSETS/"cursor.ico"))); self.tray_menu=QMenu(); self._tray_src=None; self.tray_menu.aboutToShow.connect(self.refresh_tray_menu); self.tray.setContextMenu(self.tray_menu); self.tray.show(); self.sim_timer=QTimer(self); self.sim_timer.timeout.connect(self.simulate); self.sim_timer.setInterval(int(self.config.get("simulation_interval",30)*1000)); self.sim_timer.start(); self.cleanup=QTimer(self); self.cleanup.timeout.connect(self.cleanup_bowl); self.cleanup.start(5000); self.render()
 def load(self):
  try:c=json.loads(CONFIG.read_text(encoding="utf-8")); d=cfg_default(); d.update(c); d["api_profiles"]=migrate_profiles(d); return d
  except Exception:
   d=cfg_default(); d["api_profiles"]=migrate_profiles(d); return d
 def apply_theme(self):
  qss=DARK_QSS if self.config.get("theme","light")=="dark" else LIGHT_QSS; app=QApplication.instance(); app.setStyleSheet(qss)
  for w in app.topLevelWidgets():
   if w is not self: w.setStyleSheet(qss)
 def toggle_theme(self): self.update({"theme":"dark" if self.config.get("theme","light")=="light" else "light"})
 def save_pet_profile(self,values=None):
  profiles=self.config.setdefault("pet_profiles",{}); key=self.current.name; profile=profiles.setdefault(key,{}); profile.update(values or {k:self.config.get(k) for k in ("opacity","size","auto_snap","dynamic_effects")}); self.save()
 def load_pet_profile(self):
  profile=self.config.get("pet_profiles",{}).get(self.current.name,{}); self.config.update(profile)
 def save(self):
  tmp=CONFIG.with_suffix(".tmp"); tmp.write_text(json.dumps(self.config,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(CONFIG)
 def update(self,values):
  self.config.update(values); self.save()
  if {"opacity","size","always_on_top","click_through"}&set(values): self.apply()
  self.render()
  for key,value in values.items(): self.settings_changed.emit(key,value)
 def apply(self):
  w=int(self.config.get("size",520)); self.resize(w,max(220,round(w*CANVAS[1]/CANVAS[0]))); self.setWindowOpacity(int(self.config.get("opacity",100))/100); flags=Qt.FramelessWindowHint|Qt.Tool|(Qt.WindowStaysOnTopHint if self.config.get("always_on_top",True) else Qt.WindowType(0)); self.setWindowFlags(flags); self.setAttribute(Qt.WA_TransparentForMouseEvents,bool(self.config.get("click_through",False))); self.show()
 def render(self):
  role=next((k for k,v in BUILTINS.items() if v==self.current.name),"")
  p=self.current; n=self.config.get("expression","default")
  if role=="藍色大肥魚（DeepSeek）" and self.config.get("deepseek_dark"):
   p=ASSETS/DARK_EXPRESSIONS.get(n,DARK_EXPRESSIONS["default"])
  folder=EXPR.get(role); ep=ASSETS/"legacy_chars"/folder/"sprites"/f"{n}.png" if folder and n!="default" else None; p=ep if ep and ep.exists() and not (role=="藍色大肥魚（DeepSeek）" and self.config.get("deepseek_dark")) else p; pix=QPixmap(str(p)); self.label.setPixmap(pix.scaled(self.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
 def resizeEvent(self,e): super().resizeEvent(e); self.render()
 def mousePressEvent(self,e):
  if e.button()==Qt.LeftButton:self.drag=e.globalPosition().toPoint()-self.frameGeometry().topLeft()
  elif e.button()==Qt.RightButton:
   m=self.menu(); m.exec(e.globalPosition().toPoint()); m.deleteLater()
 def mouseMoveEvent(self,e):
  if self.drag is not None and e.buttons()&Qt.LeftButton:self.move(e.globalPosition().toPoint()-self.drag); self.collide_walkers()
 def mouseReleaseEvent(self,e): self.drag=None
 def collide_walkers(self):
  for w in self.walkers:
   if self.geometry().intersects(w.geometry()): w.move(w.x(),w.y()-20)
 def menu(self):
  m=QMenu(self); m.setAttribute(Qt.WA_DeleteOnClose,False); a=m.addAction("開啟控制中心"); a.triggered.connect(self.open_panel); ps=m.addAction("目前寵物設定"); ps.triggered.connect(lambda:PetSettingsDialog(self).exec()); th=m.addAction("切換到"+("深色" if self.config.get("theme","light")=="light" else "淺色")+"模式"); th.triggered.connect(self.toggle_theme); profiles=m.addAction("API 設定檔／多模型管理"); profiles.triggered.connect(lambda:KeyDialog(self).exec()); chatmode=m.addAction("AI 對話模式："+ ("開啟" if self.config.get("ai_chat_enabled") else "關閉")); chatmode.triggered.connect(lambda: self.update({"ai_chat_enabled":not self.config.get("ai_chat_enabled",False)})); mode=m.addAction("切換到 API 模式" if self.config.get("mode")=="simulation" else "切換到模擬模式"); mode.triggered.connect(lambda:self.set_mode("api" if self.config.get("mode")=="simulation" else "simulation")); k=m.addAction("API Key／AI 對話設定"); k.triggered.connect(lambda:KeyDialog(self).exec()); vs=m.addAction("語音與 TTS 設定"); vs.triggered.connect(lambda:VoiceSettingsDialog(self).exec()); pv=m.addAction("純語音模式（Gemini Live）"); pv.triggered.connect(self.chat); c=m.addAction("與角色對話"); c.triggered.connect(self.chat); m.addSeparator(); actors=m.addMenu(f"可動角色（{len(self.walkers)}/{MAX_EXTRA}）"); actors.addAction("新增正常 DeepSeek 三方向").triggered.connect(lambda:self.add_walker("deepseek")); actors.addAction("新增黑化 DeepSeek 三方向").triggered.connect(lambda:self.add_walker("deepseek_dark")); disabled=actors.addAction("Claude/Gemini/GPT：沒有 walking sprite，禁止自動行走"); disabled.setEnabled(False); actors.addAction("移除所有額外角色").triggered.connect(self.remove_walkers); m.addAction("隨機表情").triggered.connect(self.random_expression); darkexpr=m.addMenu("黑化專屬表情"); darkexpr.setEnabled(self.is_deepseek_dark()); [darkexpr.addAction(label).triggered.connect(lambda checked=False,n=name:self.set_expression(n)) for name,label in [("dark_anger","狂怒"),("dark_smirk","冷笑"),("dark_glow","幽光"),("dark_void","虛無")]]; dark=m.addAction("DeepSeek："+ ("切換正常版" if self.config.get("deepseek_dark") else "切換黑化版")); dark.setEnabled(self.current.name in ("sprite.png","sprite-deepseek-dark.png")); dark.triggered.connect(self.toggle_deepseek_dark); m.addAction("匯入自訂角色").triggered.connect(self.import_character); m.addAction("立即掉落飯盆").triggered.connect(self.spawn_bowl); m.addAction("清除飯盆").triggered.connect(self.clear_bowl); m.addAction("切換滑鼠穿透").triggered.connect(lambda:self.update({"click_through":not self.config.get("click_through",False)})); m.addAction("回到左下角").triggered.connect(self.snap); m.addSeparator(); m.addAction("退出").triggered.connect(QApplication.quit); return m
 def refresh_tray_menu(self):
  old=self._tray_src; self.tray_menu.clear(); self._tray_src=self.menu()
  for a in self._tray_src.actions(): self.tray_menu.addAction(a)
  if old: old.deleteLater()
 def open_panel(self):
  if not self.panel:
   self.panel=Panel(self); self.settings_changed.connect(self.panel.sync_settings)
  self.panel.show(); self.panel.raise_(); self.panel.activateWindow()
 def set_mode(self,mode): self.update({"mode":mode}); self.tray.showMessage(APP_NAME,"已切換到"+mode)
 def select(self,name):
  if self.is_busy(): self.busy_notice(); return
  self.save_pet_profile(); self.current=ASSETS/name; self.load_pet_profile(); self.apply(); self.update({"character":str(self.current)})
 def set_expression(self,name): self.update({"expression":name})
 def is_deepseek_dark(self): return self.current.name=="sprite.png" and bool(self.config.get("deepseek_dark"))
 def random_expression(self):
  choices=list(DARK_EXPRESSIONS) if self.is_deepseek_dark() else ["default","expression_11","expression_12","expression_21","expression_22"]; self.set_expression(random.choice(choices))
 def toggle_deepseek_dark(self):
  if self.is_busy(): self.busy_notice(); return
  if self.current.name=="sprite.png" or self.current.name=="sprite-deepseek-dark.png": self.update({"deepseek_dark":not self.config.get("deepseek_dark",False)})
 def import_character(self):
  if self.is_busy(): self.busy_notice(); return
  src,_=QFileDialog.getOpenFileName(self,"選擇角色圖片","","圖片 (*.png *.jpg *.jpeg *.webp)");
  if not src:return
  name,ok=QInputDialog.getText(self,"角色名稱","名稱：",text="custom_character")
  if ok and name: dst=CUSTOM/(name+".png"); fit_canvas(Path(src),dst); self.current=dst; self.update({"character":str(dst)})
 def add_walker(self,prefix):
  if len(self.walkers)>=MAX_EXTRA:return
  paths={n:ASSETS/f"{prefix}_{n}.png" for n in ("front","side","back")}
  if not all(p.exists() for p in paths.values()): self.tray.showMessage(APP_NAME,"此角色缺少完整 walking sprite，已禁止啟動"); return
  w=Walker(paths,len(self.walkers)+1,self); self.walkers.append(w); w.show()
 def remove_walkers(self):
  for w in self.walkers:w.close()
  self.walkers.clear()
 def snap(self):
  s=QApplication.primaryScreen().availableGeometry(); self.move(s.left()+20,s.bottom()-self.height()-20)
 def spawn_bowl(self):
  self.clear_bowl(); self.bowl=Bowl(self); self.bowl.move(max(0,self.width()-100),20); self.bowl.fed.connect(self.feed); self.bowl.show(); self.config["bowl_time"]=datetime.now().timestamp(); self.save()
 def clear_bowl(self):
  if self.bowl:self.bowl.deleteLater(); self.bowl=None
 def cleanup_bowl(self):
  if self.bowl and datetime.now().timestamp()-self.config.get("bowl_time",0)>45:self.feed()
 def feed(self):
  self.clear_bowl(); self.config["last_event"]=f"餵食 +飯盆（{datetime.now():%H:%M:%S}）"; self.add_log(self.config["last_event"]); self.play("feed.mp3")
 def play(self,name):
  if os.environ.get("QT_QPA_PLATFORM")=="offscreen": return
  try:
   out=QAudioOutput(self); out.setVolume(.7); player=QMediaPlayer(self); player.setAudioOutput(out); player.setSource(QUrl.fromLocalFile(str(ASSETS/name)))
   player.mediaStatusChanged.connect(lambda st,p=player,o=out:(p.deleteLater(),o.deleteLater()) if st==QMediaPlayer.MediaStatus.EndOfMedia else None); player.play()
  except Exception: pass
 def add_log(self,text): self.config.setdefault("event_log",[]).append(text); self.config["event_log"]=self.config["event_log"][-100:]; self.save()
 def simulate(self):
  if self.config.get("mode")!="simulation" or not self.config.get("simulation_enabled",True):return
  debit=random.random()<.7; key="debit_min" if debit else "credit_min"; hi="debit_max" if debit else "credit_max"; amount=round(random.uniform(float(self.config.get(key,0.01)),float(self.config.get(hi,0.1))),2); amount=-amount if debit else amount; self.config["sim_balance"]=round(float(self.config.get("sim_balance",50))+amount,2); text=f"{datetime.now():%H:%M:%S} {'扣款' if debit else '充值'} {amount:+.2f}"; self.config["last_event"]=text; self.add_log(text); self.play("hit.mp3" if debit else "feed.mp3");
  if not debit:self.spawn_bowl()
  self.save()
 def refresh_api(self):
  profiles=self.config.get("api_profiles",default_profiles()); idx=max(0,min(int(self.config.get("active_profile",0)),len(profiles)-1)) if profiles else -1; profile=profiles[idx] if idx>=0 else {}; provider=profile.get("provider",self.config.get("provider","DeepSeek")); key=profile.get("key",self.config.get("api_keys",{}).get(provider,""))
  if provider not in ("DeepSeek","OpenAI") or not key: QMessageBox.warning(self,"無法查詢餘額","目前餘額查詢需要 DeepSeek 或 OpenAI Admin API Key 設定檔。"); return
  self.worker=Worker(provider,key,None,self); self.worker.done.connect(self.api_done); self.worker.start()
 def api_done(self,ok,data):
  self.worker=None
  if ok:self.config["api_balance"]=data.get("balance"); self.config["last_event"]=f"API 查詢成功：{data.get('balance')}（{data.get('source','')}）"; self.add_log(self.config["last_event"]); self.save(); QMessageBox.information(self,"API 查詢成功",self.config["last_event"])
  else: QMessageBox.warning(self,"API 查詢失敗",data.get("error","未知錯誤"))
 def is_busy(self):
  return any(getattr(self,n,None) is not None and getattr(getattr(self,n,None),"isRunning",lambda:False)() for n in ("worker","chat_worker","voice_recorder","voice_transcriber","tts_worker","live_worker"))
 def busy_notice(self): self.tray.showMessage(APP_NAME,"目前正在生成對話或語音，暫時不能切換主角色")
 def voice_profile(self):
  profiles=self.config.get("api_profiles",default_profiles()); idx=max(0,min(int(self.config.get("active_profile",0)),len(profiles)-1)) if profiles else -1; return profiles[idx] if idx>=0 else {}
 def gemini_profile(self):
  profiles=self.config.get("api_profiles",[]); active=self.voice_profile()
  if active.get("provider")=="Google Gemini": return active
  return next((x for x in profiles if x.get("provider")=="Google Gemini"),active)
 def toggle_voice(self,dialog):
  if getattr(self,"voice_recorder",None) and self.voice_recorder.isRunning(): self.voice_recorder.stop(); dialog.mic.setText("處理中…"); return
  self.voice_dialog=dialog; self.voice_recorder=VoiceRecorder(self.config.get("voice_input_mode","traditional")=="traditional",self); self.voice_recorder.partial.connect(lambda text:dialog.input.setText(text)); self.voice_recorder.level.connect(lambda n:dialog.voice_status.setText(f"錄音中… 音量 {n}%")); self.voice_recorder.finished.connect(lambda path:self.on_recorded(path,dialog)); self.voice_recorder.failed.connect(lambda e:self.voice_failed(e,dialog)); self.voice_recorder.start(); dialog.mic.setChecked(True); dialog.mic.setText("結束錄音"); dialog.voice_status.setText("錄音中…")
 def voice_failed(self,error,dialog):
  self.voice_recorder=None
  if hasattr(dialog,"pure") and dialog.pure.isChecked(): dialog.pure.setChecked(False); dialog.pure.setText("純語音")
  else: dialog.mic.setChecked(False); dialog.mic.setText("麥克風")
  dialog.voice_status.setText("語音錯誤："+error)
 def on_recorded(self,path,dialog):
  self.voice_recorder=None
  mode=self.config.get("voice_input_mode","traditional"); dialog.mic.setChecked(False); dialog.mic.setText("麥克風"); dialog.voice_status.setText("辨識中…"); self.voice_transcriber=VoiceTranscriber(path,mode,{**self.voice_profile(),"stt_model":self.config.get("stt_model","whisper-1")},self); self.voice_transcriber.finished.connect(lambda ok,text:self.on_transcribed(ok,text,dialog)); self.voice_transcriber.start()
 def on_transcribed(self,ok,text,dialog):
  self.voice_transcriber=None
  if not ok: dialog.voice_status.setText("語音辨識錯誤："+text); return
  dialog.input.setText(text); dialog.voice_status.setText("語音辨識完成");
  if self.config.get("voice_input_mode")=="traditional" or self.config.get("voice_auto_send",False): dialog.send()
 def toggle_pure_voice(self,dialog):
  if getattr(self,"live_worker",None) and self.live_worker.isRunning(): self.live_worker.cancel(); dialog.pure.setChecked(False); dialog.pure.setText("中斷中…"); dialog.voice_status.setText("正在中斷 Gemini Live…"); return
  if getattr(self,"voice_recorder",None) and self.voice_recorder.isRunning(): self.voice_recorder.stop(); dialog.pure.setText("處理中…"); return
  self.voice_dialog=dialog; self.voice_recorder=VoiceRecorder(False,self); self.voice_recorder.level.connect(lambda n:dialog.voice_status.setText(f"純語音錄音中… 音量 {n}%")); self.voice_recorder.finished.connect(lambda path:self.on_pure_recorded(path,dialog)); self.voice_recorder.failed.connect(lambda e:self.voice_failed(e,dialog)); self.voice_recorder.start(); dialog.pure.setChecked(True); dialog.pure.setText("結束純語音"); dialog.voice_status.setText("純語音錄音中…")
 def on_pure_recorded(self,path,dialog):
  self.voice_recorder=None
  dialog.pure.setChecked(False); dialog.pure.setText("純語音"); dialog.voice_status.setText("Gemini Live 處理中…"); profile=self.gemini_profile(); self.live_worker=GeminiLiveWorker(path,profile,self.memory_prompt(),self.config.get("gemini_live_model","gemini-3.8-live"),self.config.get("gemini_live_voice","Kore"),self); self.live_worker.finished.connect(lambda ok,data:self.on_live_done(ok,data,dialog)); self.live_worker.start()
 def on_live_done(self,ok,data,dialog):
  self.live_worker=None
  if not ok:
   dialog.pure.setChecked(False); dialog.pure.setText("純語音"); dialog.voice_status.setText(("Gemini Live 已中斷" if data.get("cancelled") else "Gemini Live 逾時" if data.get("timeout") else "Gemini Live 錯誤："+data.get("error","未知錯誤"))); return
  dialog.voice_status.setText("Gemini Live 完成"); text=data.get("text",""); self.remember_live_transcript(text)
  replies=[x[len("Gemini："):] for x in text.splitlines() if x.startswith("Gemini：")]
  if replies: self.show_bubble(replies[-1][:180],False)
  if data.get("audio"): self.play_file(data["audio"])
 def speak(self,text):
  mode=self.config.get("tts_mode","off")
  if mode=="off" or not text.strip(): return
  self.tts_worker=TTSWorker(text,mode,{**self.voice_profile(),"tts_model":self.config.get("tts_model"),"voice":self.config.get("tts_voice")},self); self.tts_worker.finished.connect(self.on_tts_done); self.tts_worker.start()
 def on_tts_done(self,ok,msg):
  self.tts_worker=None
  if not ok: self.add_log("TTS錯誤："+msg)
  elif msg: self.play_file(msg)
 def play_file(self,path):
  try:
   self.audio_output=QAudioOutput(self); self.audio_output.setVolume(.9); self.audio_player=QMediaPlayer(self); self.audio_player.setAudioOutput(self.audio_output); self.audio_player.setSource(QUrl.fromLocalFile(path)); self.audio_player.play()
  except Exception as e: self.add_log("音訊播放錯誤："+str(e))
 def chat(self):
  if getattr(self,"chat_dialog",None) and self.chat_dialog.isVisible(): self.chat_dialog.raise_(); self.chat_dialog.activateWindow(); return
  self.chat_dialog=ChatDialog(self); self.settings_changed.connect(self.chat_dialog.sync_settings); self.chat_dialog.finished.connect(lambda _: setattr(self,"chat_dialog",None)); self.chat_dialog.show(); self.chat_dialog.raise_(); self.chat_dialog.activateWindow()
 def show_bubble(self,text,thought=False):
  if not hasattr(self,"bubble"): self.bubble=SpeechBubble(self)
  self.bubble.show_message(text,thought)
 def remember(self,role,content):
  items=self.config.setdefault("short_memory",[]); items.append({"role":role,"content":content,"time":datetime.now().isoformat(timespec="seconds")}); limit=max(1,int(self.config.get("short_memory_limit",20))); self.config["short_memory"]=items[-limit*2:]; self.save(); self.settings_changed.emit("short_memory",list(self.config["short_memory"]))
 def memory_prompt(self):
  long=self.config.get("long_memory",[]); short=self.config.get("short_memory",[]); parts=["你是桌面上的可愛角色。請用繁體中文、簡短自然地回應使用者，不要輸出思考過程。"]
  if long: parts.append("長期記憶（請在相關時使用，不要逐條念出）：\n"+"\n".join("- "+x for x in long))
  if short: parts.append("最近對話記憶（由舊到新）：\n"+"\n".join(("使用者：" if x.get("role")=="user" else "角色：")+x.get("content","") for x in short))
  return "\n\n".join(parts)
 def remember_live_transcript(self,text):
  for line in text.splitlines():
   if line.startswith("使用者："): self.remember("user",line[len("使用者："):].strip())
   elif line.startswith("Gemini："): self.remember("assistant",line[len("Gemini："):].strip())
 def handle_chat(self,text,dialog,index=0):
  dialog.add_message("你",text); self.remember("user",text); self.show_bubble("思考中…",True); profiles=self.config.get("api_profiles",default_profiles()); index=max(0,min(index,len(profiles)-1)) if profiles else -1
  self.update({"active_profile":index}); profile=profiles[index] if index>=0 else {}
  if not self.config.get("ai_chat_enabled",False) or (profile.get("provider")!="Ollama" and not profile.get("key")):
   QTimer.singleShot(450,lambda:self.chat_result(dialog,True,{"message":random.choice(LINES)})); return
  prompt=self.memory_prompt()+"\n\n請回應最近一則使用者訊息。"
  self.chat_worker=Worker(profile,prompt,None,self); self.chat_worker.done.connect(lambda ok,data:self.chat_result(dialog,ok,data)); self.chat_worker.start()
 def chat_result(self,dialog,ok,data):
  self.chat_worker=None
  reply=data.get("message") if ok else random.choice(LINES); self.remember("assistant",reply); self.show_bubble(reply,False); dialog.add_message("角色",reply); self.play("hit.mp3") if self.is_deepseek_dark() else None; self.speak(reply)
  if not ok: self.add_log("AI 對話失敗，改用隨機文句："+data.get("error","未知錯誤"))

def main():
 configure_tls(); os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING","1"); os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY","PassThrough"); app=QApplication(sys.argv); app.setApplicationName(APP_NAME); pet=Pet(); pet.snap(); return app.exec()
if __name__=="__main__":sys.exit(main())

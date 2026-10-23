from __future__ import annotations
import json, os, random, sys, urllib.request, urllib.error, urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional
from PIL import Image
from PySide6.QtCore import QPoint, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QApplication,QCheckBox,QComboBox,QDialog,QDialogButtonBox,
 QFileDialog,QDoubleSpinBox,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,
 QMainWindow,QMenu,QMessageBox,QPushButton,QSpinBox,QSystemTrayIcon,QTabWidget,
 QTextEdit,QVBoxLayout,QWidget,QStyle,QInputDialog)

APP_NAME="Python Desktop Pet v4"; ROOT=Path(__file__).resolve().parent; ASSETS=ROOT/"assets"; CUSTOM=ROOT/"custom_characters"; CONFIG=ROOT/"pet_config.json"; CANVAS=(1536,1024); MAX_EXTRA=4
BUILTINS={"藍色大肥魚（DeepSeek）":"sprite.png","GPT 龍娘":"sprite-gpt.png","大小姐 Claude":"sprite-claude.png","北美貓娘 Gemini":"sprite-gemini.png"}
EXPR={"GPT 龍娘":"gpt","大小姐 Claude":"claude","北美貓娘 Gemini":"gemini"}
LINES=["今天也要記得休息一下。","我有看到你在努力喔。","要不要餵我一點飯？","目前沒有啟用 AI 對話，我先用隨機文句陪你。","桌面巡邏完成，暫時安全。","今天的狀態：可愛但有點餓。","別忘了喝水。","我會在這裡陪著你。"]

def fit_canvas(src:Path,dst:Path):
 with Image.open(src).convert("RGBA") as im:
  im.thumbnail(CANVAS,Image.Resampling.LANCZOS); out=Image.new("RGBA",CANVAS,(0,0,0,0)); out.alpha_composite(im,((CANVAS[0]-im.width)//2,(CANVAS[1]-im.height)//2)); dst.parent.mkdir(parents=True,exist_ok=True); out.save(dst,"PNG")
def cfg_default(): return {"opacity":100,"size":520,"always_on_top":True,"click_through":False,"auto_snap":True,"auto_feed":True,"interval":30,"mode":"simulation","simulation_enabled":True,"simulation_interval":30,"sim_balance":50.0,"debit_min":.01,"debit_max":.10,"credit_min":1.0,"credit_max":5.0,"api_keys":{},"api_profiles":default_profiles(),"active_profile":0,"provider":"DeepSeek","ai_chat_enabled":False,"deepseek_dark":False,"character":str(ASSETS/"sprite.png"),"expression":"default","event_log":[]}

PROVIDERS=["DeepSeek","OpenAI","Google Gemini","Anthropic","Mistral","xAI","z.ai","GLM","Ollama","Kiwi","OpenCode","OpenAI 相容自訂端點"]

def default_profiles():
 return [{"name":"DeepSeek 預設","provider":"DeepSeek","key":"","endpoint":"https://api.deepseek.com","model":"deepseek-chat"}]

def migrate_profiles(config):
 if config.get("api_profiles") is not None: return config["api_profiles"]
 profiles=[]
 for provider,key in config.get("api_keys",{}).items(): profiles.append({"name":provider+" 預設","provider":provider,"key":key,"endpoint":"","model":""})
 return profiles or default_profiles()

def chat_request(profile,prompt):
 provider=profile.get("provider","DeepSeek"); key=profile.get("key",""); endpoint=profile.get("endpoint","").strip(); model=profile.get("model","")
 if provider=="Google Gemini":
  if not key: raise RuntimeError("Google Gemini 需要 API Key")
  model=model or "gemini-2.5-flash"; base=endpoint or "https://generativelanguage.googleapis.com/v1beta"; url=base.rstrip("/")+f"/models/{model}:generateContent?key={urllib.parse.quote(key)}"; headers={"content-type":"application/json"}; body={"contents":[{"role":"user","parts":[{"text":prompt}]}],"generationConfig":{"maxOutputTokens":160}}
 elif provider=="Anthropic":
  url=(endpoint or "https://api.anthropic.com/v1").rstrip("/")+"/messages"; headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"}; body={"model":model or "claude-3-5-haiku-latest","max_tokens":160,"messages":[{"role":"user","content":prompt}]}
 else:
  bases={"DeepSeek":"https://api.deepseek.com","OpenAI":"https://api.openai.com/v1","Mistral":"https://api.mistral.ai/v1","xAI":"https://api.x.ai/v1","z.ai":"https://api.z.ai/api/paas/v4","GLM":"https://open.bigmodel.cn/api/paas/v4","Ollama":"http://localhost:11434/v1"}
  base=endpoint or bases.get(provider,"")
  if not base: raise RuntimeError(provider+" 沒有固定端點，請在 API 設定檔填入 OpenAI-compatible 端點")
  url=base.rstrip("/")+"/chat/completions"; headers={"content-type":"application/json"}
  if key: headers["Authorization"]="Bearer "+key
  defaults={"DeepSeek":"deepseek-chat","OpenAI":"gpt-4o-mini","Mistral":"mistral-small-latest","xAI":"grok-3-mini","z.ai":"glm-4.5-flash","GLM":"glm-4.5-flash","Ollama":"llama3.2"}; body={"model":model or defaults.get(provider,""),"messages":[{"role":"user","content":prompt}],"max_tokens":160}
 req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method="POST")
 with urllib.request.urlopen(req,timeout=30) as r: data=json.loads(r.read().decode())
 if provider=="Google Gemini": text=data["candidates"][0]["content"]["parts"][0]["text"]
 elif provider=="Anthropic": text=data["content"][0]["text"]
 else: text=data["choices"][0]["message"]["content"]
 return {"message":text,"raw":data}

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

class SpeechBubble(QLabel):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setWordWrap(True); self.setAlignment(Qt.AlignCenter); self.setAttribute(Qt.WA_TransparentForMouseEvents); self.hide()
 def show_message(self,text,thought=False):
  self.setText(text); self.setStyleSheet("QLabel{color:#222;background:%s;border:2px solid #555;border-radius:16px;padding:8px 12px;font-size:15px;}" % ("#e8e8e8" if thought else "#fffdf2")); self.setMaximumWidth(max(180,min(360,self.pet.width()-20))); self.adjustSize(); self.resize(min(360,max(180,self.sizeHint().width())),max(44,self.sizeHint().height())); self.move(max(5,(self.pet.width()-self.width())//2),8); self.raise_(); self.show(); QTimer.singleShot(6500,self.hide)

class ChatDialog(QDialog):
 def __init__(self,pet):
  super().__init__(None,Qt.FramelessWindowHint|Qt.Tool); self.pet=pet; self.setWindowTitle("角色對話"); self.setMinimumSize(390,330); self.setStyleSheet("QDialog{background:#fff8e8;border:2px solid #7b6650;border-radius:14px;} QLabel{color:#4b3b2a;} QLineEdit,QTextEdit,QComboBox{background:#fffdf8;border:1px solid #c9b79f;border-radius:8px;padding:5px;}")
  root=QVBoxLayout(self); title=QLabel("角色聊天（可選擇模型）"); title.setStyleSheet("font-weight:bold;font-size:16px;"); root.addWidget(title); self.profile=QComboBox(); self.reload_profiles(); root.addWidget(self.profile); self.history=QTextEdit(); self.history.setReadOnly(True); root.addWidget(self.history); row=QHBoxLayout(); self.input=QLineEdit(); self.input.setPlaceholderText("輸入訊息…"); self.input.returnPressed.connect(self.send); row.addWidget(self.input); send=QPushButton("送出"); send.clicked.connect(self.send); row.addWidget(send); root.addLayout(row); manage=QPushButton("管理 API 設定檔"); manage.clicked.connect(self.manage_profiles); root.addWidget(manage); close=QPushButton("收起聊天框"); close.clicked.connect(self.close); root.addWidget(close); self.input.setFocus()
 def reload_profiles(self):
  self.profile.clear(); items=self.pet.config.get("api_profiles",default_profiles()); self.profile.addItems([f"{x.get('name','未命名')}｜{x.get('provider','')}｜{x.get('model') or '預設模型'}" for x in items]); self.profile.setCurrentIndex(max(0,min(self.pet.config.get("active_profile",0),len(items)-1)) if items else -1)
 def showEvent(self,e): super().showEvent(e); self.move(self.pet.x()+max(0,(self.pet.width()-self.width())//2),self.pet.y()+max(20,self.pet.height()//3))
 def add_message(self,who,text): self.history.append(f"<b>{who}：</b>{text}")
 def manage_profiles(self):
  d=KeyDialog(self.pet)
  if d.exec()==QDialog.Accepted:self.reload_profiles()
 def send(self):
  text=self.input.text().strip()
  if text: self.input.clear(); self.pet.handle_chat(text,self,self.profile.currentIndex())

class Bowl(QLabel):
 fed=Signal()
 def __init__(self,parent):
  super().__init__(parent); self.host=parent; self.drag=None; self.setText("🍚"); self.setAlignment(Qt.AlignCenter); self.setStyleSheet("font-size:40px;background:rgba(255,255,255,210);border-radius:24px;padding:5px;"); self.resize(78,78)
 def mousePressEvent(self,e):
  if e.button()==Qt.LeftButton:self.drag=e.globalPosition().toPoint()-self.pos(); e.accept()
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
  self.label=QLabel(self); self.label.setStyleSheet("background:transparent"); self.resize(230,180); self.render_image()
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
  self.move(nx,self.y()); self.avoid()
 def show_side(self): self.path=self.paths["side"]; self.render_image()
 def avoid(self):
  if self.geometry().intersects(self.pet.geometry()): self.move(self.x(),self.y()-20)
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
  super().__init__(pet); self.pet=pet; self.setWindowTitle("API 設定檔管理"); self.resize(620,420); self.items=[dict(x) for x in pet.config.get("api_profiles",default_profiles())]; root=QVBoxLayout(self); row=QHBoxLayout(); self.list=QListWidget(); row.addWidget(self.list,1); form=QFormLayout(); self.name=QLineEdit(); self.provider=QComboBox(); self.provider.addItems(PROVIDERS); self.key=QLineEdit(); self.key.setEchoMode(QLineEdit.Password); self.endpoint=QLineEdit(); self.model=QLineEdit(); form.addRow("設定檔名稱",self.name); form.addRow("供應商",self.provider); form.addRow("API Key",self.key); form.addRow("端點 URL",self.endpoint); form.addRow("模型",self.model); row.addLayout(form,2); root.addLayout(row); buttons=QHBoxLayout(); add=QPushButton("新增設定檔"); add.clicked.connect(self.add); remove=QPushButton("刪除選取"); remove.clicked.connect(self.remove); buttons.addWidget(add); buttons.addWidget(remove); root.addLayout(buttons); note=QLabel("Ollama 預設端點為 http://localhost:11434/v1，可不填 Key；自訂端點需提供 OpenAI-compatible /chat/completions。多個設定檔會出現在聊天框的模型選擇器。"); note.setWordWrap(True); root.addWidget(note); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.save); b.rejected.connect(self.reject); root.addWidget(b); self.list.currentRowChanged.connect(self.load_item); self.refresh_list(); self.list.setCurrentRow(0)
 def refresh_list(self): self.list.clear(); self.list.addItems([x.get("name",x.get("provider","未命名")) for x in self.items])
 def load_item(self,row):
  if 0<=row<len(self.items):
   x=self.items[row]; self.name.setText(x.get("name","")); self.provider.setCurrentText(x.get("provider","DeepSeek")); self.key.setText(x.get("key","")); self.endpoint.setText(x.get("endpoint","")); self.model.setText(x.get("model",""))
 def current(self): return {"name":self.name.text().strip() or "未命名","provider":self.provider.currentText(),"key":self.key.text().strip(),"endpoint":self.endpoint.text().strip(),"model":self.model.text().strip()}
 def store_current(self):
  row=self.list.currentRow()
  if 0<=row<len(self.items): self.items[row]=self.current()
 def add(self): self.store_current(); self.items.append({"name":"新設定檔","provider":"OpenAI","key":"","endpoint":"","model":"gpt-4o-mini"}); self.refresh_list(); self.list.setCurrentRow(len(self.items)-1)
 def remove(self):
  row=self.list.currentRow()
  if 0<=row<len(self.items): self.items.pop(row); self.refresh_list(); self.list.setCurrentRow(max(0,row-1))
 def save(self):
  self.store_current(); self.pet.config["api_profiles"]=self.items; self.pet.config["active_profile"]=max(0,min(int(self.pet.config.get("active_profile",0)),len(self.items)-1)) if self.items else 0; self.pet.save(); self.accept()

class SimulationDialog(QDialog):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setWindowTitle("模擬模式控制"); f=QFormLayout(self); self.enabled=QCheckBox("啟用自動事件"); self.enabled.setChecked(pet.config.get("simulation_enabled",True)); f.addRow(self.enabled); self.balance=QDoubleSpinBox(); self.balance.setRange(-1e9,1e9); self.balance.setDecimals(2); self.balance.setValue(float(pet.config.get("sim_balance",50))); f.addRow("餘額",self.balance); self.interval=QSpinBox(); self.interval.setRange(1,86400); self.interval.setValue(int(pet.config.get("simulation_interval",30))); self.interval.setSuffix(" 秒"); f.addRow("事件間隔",self.interval)
  for key,label,lo,hi in [("debit_min","扣款下限",0,9999),("debit_max","扣款上限",0,9999),("credit_min","充值下限",0,9999),("credit_max","充值上限",0,9999)]:
   w=QDoubleSpinBox(); w.setRange(lo,hi); w.setDecimals(2); w.setValue(float(pet.config.get(key,1))); setattr(self,key,w); f.addRow(label,w)
  b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.save); b.rejected.connect(self.reject); f.addRow(b); now=QPushButton("立即模擬事件"); now.clicked.connect(pet.simulate); f.addRow(now)
 def save(self):
  c={"simulation_enabled":self.enabled.isChecked(),"sim_balance":self.balance.value(),"simulation_interval":self.interval.value()}; c.update({k:getattr(self,k).value() for k in ("debit_min","debit_max","credit_min","credit_max")}); self.pet.config.update(c); self.pet.save(); self.pet.sim_timer.setInterval(int(self.interval.value()*1000)); self.accept()

class Panel(QDialog):
 def __init__(self,pet):
  super().__init__(pet); self.pet=pet; self.setWindowTitle("Python Desktop Pet v4｜控制面板"); self.resize(720,600); root=QVBoxLayout(self); tabs=QTabWidget(); root.addWidget(tabs)
  tab=QWidget(); h=QHBoxLayout(tab); self.list=QListWidget(); self.paths=[]
  for label,name in BUILTINS.items(): self.list.addItem(label); self.paths.append(ASSETS/name)
  self.list.currentRowChanged.connect(self.preview); h.addWidget(self.list); col=QVBoxLayout(); self.pic=QLabel(); self.pic.setMinimumSize(350,250); self.pic.setAlignment(Qt.AlignCenter); col.addWidget(self.pic); use=QPushButton("套用角色"); use.clicked.connect(self.use); col.addWidget(use); imp=QPushButton("匯入自訂角色"); imp.clicked.connect(pet.import_character); col.addWidget(imp); h.addLayout(col); tabs.addTab(tab,"角色與表情"); self.list.setCurrentRow(0)
  exp=QWidget(); ef=QFormLayout(exp); self.expr=QComboBox(); self.expr.addItems(["default","expression_11","expression_12","expression_21","expression_22"]); self.expr.setCurrentText(pet.config.get("expression","default")); ef.addRow("舊表情差分",self.expr); applye=QPushButton("套用表情"); applye.clicked.connect(lambda:pet.set_expression(self.expr.currentText())); ef.addRow(applye); self.expr_note=QLabel("Claude、Gemini、GPT 的舊表情已接入；沒有 walking sprite 的角色不會自動行走。"); self.expr_note.setWordWrap(True); ef.addRow(self.expr_note); tabs.addTab(exp,"表情差分")
  ap=QWidget(); af=QFormLayout(ap); self.opacity=QSpinBox(); self.opacity.setRange(20,100); self.opacity.setValue(pet.config.get("opacity",100)); af.addRow("透明度 %",self.opacity); self.size=QSpinBox(); self.size.setRange(180,1000); self.size.setValue(pet.config.get("size",520)); af.addRow("寬度 px",self.size); self.snap=QCheckBox("自動貼邊"); self.snap.setChecked(pet.config.get("auto_snap",True)); af.addRow(self.snap); applya=QPushButton("套用外觀"); applya.clicked.connect(self.apply_appearance); af.addRow(applya); tabs.addTab(ap,"外觀與 DPI")
  sim=QWidget(); sf=QVBoxLayout(sim); self.status=QLabel(); self.status.setWordWrap(True); sf.addWidget(self.status); b=QPushButton("模擬模式設定"); b.clicked.connect(lambda:(SimulationDialog(pet).exec(),self.refresh())); sf.addWidget(b); b=QPushButton("立即模擬事件"); b.clicked.connect(lambda:(pet.simulate(),self.refresh())); sf.addWidget(b); self.log=QTextEdit(); self.log.setReadOnly(True); sf.addWidget(self.log); tabs.addTab(sim,"模擬與事件紀錄"); self.refresh()
  api=QWidget(); q=QVBoxLayout(api); self.api_status=QLabel("API 模式會使用目前供應商的實際查詢；DeepSeek 使用官方 /user/balance。"); self.api_status.setWordWrap(True); q.addWidget(self.api_status); k=QPushButton("API Key 與 AI 對話設定"); k.clicked.connect(lambda:KeyDialog(pet).exec()); q.addWidget(k); r=QPushButton("立即查詢 API 餘額"); r.clicked.connect(pet.refresh_api); q.addWidget(r); chat=QPushButton("與角色對話"); chat.clicked.connect(pet.chat); q.addWidget(chat); q.addStretch(); tabs.addTab(api,"API 與對話")
  close=QPushButton("關閉"); close.clicked.connect(self.close); root.addWidget(close)
 def preview(self,row):
  if 0<=row<len(self.paths): self.pic.setPixmap(QPixmap(str(self.paths[row])).scaled(self.pic.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
 def use(self):
  row=self.list.currentRow()
  if 0<=row<len(self.paths): self.pet.select(self.paths[row].name)
 def apply_appearance(self): self.pet.update({"opacity":self.opacity.value(),"size":self.size.value(),"auto_snap":self.snap.isChecked()})
 def refresh(self):
  self.status.setText(f"模式：{self.pet.config.get('mode')}\n模擬餘額：{float(self.pet.config.get('sim_balance',0)):.2f}\n最後事件：{self.pet.config.get('last_event','尚未發生')}"); self.log.setPlainText("\n".join(self.pet.config.get("event_log",[])))

class Pet(QMainWindow):
 def __init__(self):
  super().__init__(); self.config=self.load(); self.current=Path(self.config.get("character",ASSETS/"sprite.png")); self.drag=None; self.bowl=None; self.walkers=[]; self.worker=None; self.panel=None; self.label=QLabel(self); self.label.setStyleSheet("background:transparent"); self.setCentralWidget(self.label); self.setWindowTitle(APP_NAME); self.setAttribute(Qt.WA_TranslucentBackground); self.apply(); self.tray=QSystemTrayIcon(self); self.tray.setIcon(QIcon(str(ASSETS/"cursor.ico"))); self.tray.setContextMenu(self.menu()); self.tray.show(); self.sim_timer=QTimer(self); self.sim_timer.timeout.connect(self.simulate); self.sim_timer.setInterval(int(self.config.get("simulation_interval",30)*1000)); self.sim_timer.start(); self.cleanup=QTimer(self); self.cleanup.timeout.connect(self.cleanup_bowl); self.cleanup.start(5000); self.render()
 def load(self):
  try:c=json.loads(CONFIG.read_text(encoding="utf-8")); d=cfg_default(); d.update(c); d["api_profiles"]=migrate_profiles(d); return d
  except Exception:
   d=cfg_default(); d["api_profiles"]=migrate_profiles(d); return d
 def save(self): CONFIG.write_text(json.dumps(self.config,ensure_ascii=False,indent=2),encoding="utf-8")
 def update(self,values): self.config.update(values); self.save(); self.apply(); self.render()
 def apply(self):
  w=int(self.config.get("size",520)); self.resize(w,max(220,round(w*CANVAS[1]/CANVAS[0]))); self.setWindowOpacity(int(self.config.get("opacity",100))/100); flags=Qt.FramelessWindowHint|Qt.Tool|(Qt.WindowStaysOnTopHint if self.config.get("always_on_top",True) else Qt.WindowType(0)); self.setWindowFlags(flags); self.setAttribute(Qt.WA_TransparentForMouseEvents,bool(self.config.get("click_through",False))); self.show()
 def render(self):
  role=next((k for k,v in BUILTINS.items() if v==self.current.name),"")
  p=self.current
  if p.name=="sprite.png" and self.config.get("deepseek_dark") and (ASSETS/"sprite-deepseek-dark.png").exists(): p=ASSETS/"sprite-deepseek-dark.png"
  n=self.config.get("expression","default"); folder=EXPR.get(role); ep=ASSETS/"legacy_chars"/folder/"sprites"/f"{n}.png" if folder and n!="default" else None; p=ep if ep and ep.exists() else p; pix=QPixmap(str(p)); self.label.setPixmap(pix.scaled(self.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
 def resizeEvent(self,e): super().resizeEvent(e); self.render()
 def mousePressEvent(self,e):
  if e.button()==Qt.LeftButton:self.drag=e.globalPosition().toPoint()-self.frameGeometry().topLeft()
  elif e.button()==Qt.RightButton:self.menu().exec(e.globalPosition().toPoint())
 def mouseMoveEvent(self,e):
  if self.drag is not None and e.buttons()&Qt.LeftButton:self.move(e.globalPosition().toPoint()-self.drag); self.collide_walkers()
 def mouseReleaseEvent(self,e): self.drag=None
 def collide_walkers(self):
  for w in self.walkers:
   if self.geometry().intersects(w.geometry()): w.move(w.x(),w.y()-20)
 def menu(self):
  m=QMenu(self); a=m.addAction("開啟控制面板"); a.triggered.connect(self.open_panel); profiles=m.addAction("API 設定檔／多模型管理"); profiles.triggered.connect(lambda:KeyDialog(self).exec()); chatmode=m.addAction("AI 對話模式："+ ("開啟" if self.config.get("ai_chat_enabled") else "關閉")); chatmode.triggered.connect(lambda: self.update({"ai_chat_enabled":not self.config.get("ai_chat_enabled",False)})); mode=m.addAction("切換到 API 模式" if self.config.get("mode")=="simulation" else "切換到模擬模式"); mode.triggered.connect(lambda:self.set_mode("api" if self.config.get("mode")=="simulation" else "simulation")); k=m.addAction("API Key／AI 對話設定"); k.triggered.connect(lambda:KeyDialog(self).exec()); c=m.addAction("與角色對話"); c.triggered.connect(self.chat); m.addSeparator(); actors=m.addMenu(f"可動角色（{len(self.walkers)}/{MAX_EXTRA}）"); actors.addAction("新增正常 DeepSeek 三方向").triggered.connect(lambda:self.add_walker("deepseek")); actors.addAction("新增黑化 DeepSeek 三方向").triggered.connect(lambda:self.add_walker("deepseek_dark")); disabled=actors.addAction("Claude/Gemini/GPT：沒有 walking sprite，禁止自動行走"); disabled.setEnabled(False); actors.addAction("移除所有額外角色").triggered.connect(self.remove_walkers); m.addAction("隨機表情").triggered.connect(self.random_expression); dark=m.addAction("DeepSeek："+ ("切換正常版" if self.config.get("deepseek_dark") else "切換黑化版")); dark.setEnabled(self.current.name in ("sprite.png","sprite-deepseek-dark.png")); dark.triggered.connect(self.toggle_deepseek_dark); m.addAction("匯入自訂角色").triggered.connect(self.import_character); m.addAction("立即掉落飯盆").triggered.connect(self.spawn_bowl); m.addAction("清除飯盆").triggered.connect(self.clear_bowl); m.addAction("切換滑鼠穿透").triggered.connect(lambda:self.update({"click_through":not self.config.get("click_through",False)})); m.addAction("回到左下角").triggered.connect(self.snap); m.addSeparator(); m.addAction("退出").triggered.connect(QApplication.quit); return m
 def open_panel(self):
  if not self.panel:self.panel=Panel(self)
  self.panel.show(); self.panel.raise_(); self.panel.activateWindow()
 def set_mode(self,mode): self.update({"mode":mode}); self.tray.showMessage(APP_NAME,"已切換到"+mode)
 def select(self,name): self.current=ASSETS/name; self.update({"character":str(self.current)}); self.render()
 def set_expression(self,name): self.update({"expression":name})
 def random_expression(self):
  self.set_expression(random.choice(["default","expression_11","expression_12","expression_21","expression_22"]))
 def toggle_deepseek_dark(self):
  if self.current.name=="sprite.png" or self.current.name=="sprite-deepseek-dark.png": self.update({"deepseek_dark":not self.config.get("deepseek_dark",False)})
 def import_character(self):
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
   from PySide6.QtMultimedia import QSoundEffect
   sound=QSoundEffect(self); sound.setSource(__import__('PySide6').QtCore.QUrl.fromLocalFile(str(ASSETS/name))); sound.setVolume(.7); sound.play(); self._sound=sound
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
  if ok:self.config["api_balance"]=data.get("balance"); self.config["last_event"]=f"API 查詢成功：{data.get('balance')}（{data.get('source','')}）"; self.add_log(self.config["last_event"]); self.save(); QMessageBox.information(self,"API 查詢成功",self.config["last_event"])
  else: QMessageBox.warning(self,"API 查詢失敗",data.get("error","未知錯誤"))
 def chat(self):
  if getattr(self,"chat_dialog",None) and self.chat_dialog.isVisible(): self.chat_dialog.raise_(); self.chat_dialog.activateWindow(); return
  self.chat_dialog=ChatDialog(self); self.chat_dialog.finished.connect(lambda _: setattr(self,"chat_dialog",None)); self.chat_dialog.show(); self.chat_dialog.raise_(); self.chat_dialog.activateWindow()
 def show_bubble(self,text,thought=False):
  if not hasattr(self,"bubble"): self.bubble=SpeechBubble(self)
  self.bubble.show_message(text,thought)
 def handle_chat(self,text,dialog,index=0):
  dialog.add_message("你",text); self.show_bubble("思考中…",True); profiles=self.config.get("api_profiles",default_profiles()); index=max(0,min(index,len(profiles)-1)) if profiles else -1
  self.config["active_profile"]=index; self.save(); profile=profiles[index] if index>=0 else {}
  if not self.config.get("ai_chat_enabled",False) or (profile.get("provider")!="Ollama" and not profile.get("key")):
   QTimer.singleShot(450,lambda:self.chat_result(dialog,True,{"message":random.choice(LINES)})); return
  prompt="你是桌面上的可愛角色。請用繁體中文、簡短自然地回應使用者，不要輸出思考過程。使用者說："+text
  self.chat_worker=Worker(profile,prompt,self); self.chat_worker.done.connect(lambda ok,data:self.chat_result(dialog,ok,data)); self.chat_worker.start()
 def chat_result(self,dialog,ok,data):
  reply=data.get("message") if ok else random.choice(LINES); self.show_bubble(reply,False); dialog.add_message("角色",reply)
  if not ok: self.add_log("AI 對話失敗，改用隨機文句："+data.get("error","未知錯誤"))

def main():
 os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING","1"); os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY","PassThrough"); app=QApplication(sys.argv); app.setApplicationName(APP_NAME); pet=Pet(); pet.snap(); return app.exec()
if __name__=="__main__":sys.exit(main())

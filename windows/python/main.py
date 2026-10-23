from __future__ import annotations
import json, os, random, sys, urllib.request, urllib.error
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
BUILTINS={"藍色大肥魚（DeepSeek）":"sprite.png","GPT 龍娘":"sprite-gpt.png","大小姐 Claude":"sprite-claude.png","北美貓娘 Gemini":"sprite-gemini.png","DeepSeek 離線抱盆":"sprite-deepseek-offline.png"}
EXPR={"GPT 龍娘":"gpt","大小姐 Claude":"claude","北美貓娘 Gemini":"gemini"}
LINES=["今天也要記得休息一下。","我有看到你在努力喔。","要不要餵我一點飯？","目前沒有啟用 AI 對話，我先用隨機文句陪你。","桌面巡邏完成，暫時安全。","今天的狀態：可愛但有點餓。","別忘了喝水。","我會在這裡陪著你。"]

def fit_canvas(src:Path,dst:Path):
 with Image.open(src).convert("RGBA") as im:
  im.thumbnail(CANVAS,Image.Resampling.LANCZOS); out=Image.new("RGBA",CANVAS,(0,0,0,0)); out.alpha_composite(im,((CANVAS[0]-im.width)//2,(CANVAS[1]-im.height)//2)); dst.parent.mkdir(parents=True,exist_ok=True); out.save(dst,"PNG")
def cfg_default(): return {"opacity":100,"size":520,"always_on_top":True,"click_through":False,"auto_snap":True,"auto_feed":True,"interval":30,"mode":"simulation","simulation_enabled":True,"simulation_interval":30,"sim_balance":50.0,"debit_min":.01,"debit_max":.10,"credit_min":1.0,"credit_max":5.0,"api_keys":{},"provider":"DeepSeek","ai_chat_enabled":False,"character":str(ASSETS/"sprite.png"),"expression":"default","event_log":[]}

def api_request(provider,key,chat=None):
 if provider=="DeepSeek": base="https://api.deepseek.com"; headers={"Authorization":f"Bearer {key}"}
 elif provider=="OpenAI": base="https://api.openai.com/v1"; headers={"Authorization":f"Bearer {key}"}
 elif provider=="Anthropic": base="https://api.anthropic.com/v1"; headers={"x-api-key":key,"anthropic-version":"2023-06-01"}
 else: raise RuntimeError("目前只支援 DeepSeek、OpenAI、Anthropic 的 API 模式")
 if chat:
  if provider=="Anthropic": body={"model":"claude-3-5-haiku-latest","max_tokens":80,"messages":[{"role":"user","content":chat}]}; headers["content-type"]="application/json"; url=base+"/messages"
  else: body={"model":"deepseek-chat" if provider=="DeepSeek" else "gpt-4o-mini","messages":[{"role":"user","content":chat}],"max_tokens":80}; headers["content-type"]="application/json"; url=base+"/chat/completions"
  req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method="POST")
  with urllib.request.urlopen(req,timeout=20) as r: data=json.loads(r.read().decode())
  text=data["content"][0]["text"] if provider=="Anthropic" else data["choices"][0]["message"]["content"]
  return {"message":text,"raw":data}
 if provider=="DeepSeek":
  req=urllib.request.Request(base+"/user/balance",headers={**headers,"Accept":"application/json"})
  with urllib.request.urlopen(req,timeout=15) as r: data=json.loads(r.read().decode())
  bs=data.get("balance_infos",[]); amount=next((b.get("total_balance") for b in bs if b.get("currency")=="CNY"),None)
  if amount is None and bs: amount=bs[0].get("total_balance")
  return {"balance":float(amount or 0),"raw":data,"source":"DeepSeek /user/balance"}
 if provider=="OpenAI":
  req=urllib.request.Request(base+"/organization/costs?limit=1",headers=headers)
  with urllib.request.urlopen(req,timeout=15) as r: data=json.loads(r.read().decode())
  total=sum(float(x.get("amount",{}).get("value",0)) for x in data.get("data",[])); return {"balance":-total,"raw":data,"source":"OpenAI organization costs (admin key)"}
 raise RuntimeError("Anthropic API 需要組織管理權限；請使用官方 cost report endpoint 或切換 DeepSeek/OpenAI")

class Worker(QThread):
 done=Signal(bool,dict)
 def __init__(self,provider,key,chat=None,parent=None): super().__init__(parent); self.provider=provider; self.key=key; self.chat=chat
 def run(self):
  try:self.done.emit(True,api_request(self.provider,self.key,self.chat))
  except Exception as e:self.done.emit(False,{"error":str(e)})

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
  super().__init__(pet); self.pet=pet; self.setWindowTitle("API Key 管理"); f=QFormLayout(self); self.provider=QComboBox(); self.provider.addItems(["DeepSeek","OpenAI","Anthropic"]); self.provider.setCurrentText(pet.config.get("provider","DeepSeek")); f.addRow("供應商",self.provider); self.key=QLineEdit(pet.config.get("api_keys",{}).get(self.provider.currentText(),"")); self.key.setEchoMode(QLineEdit.Password); f.addRow("API Key",self.key); self.provider.currentTextChanged.connect(lambda p:self.key.setText(pet.config.get("api_keys",{}).get(p,""))); self.chat=QCheckBox("啟用 AI 對話模式（未勾選時使用隨機文句）"); self.chat.setChecked(pet.config.get("ai_chat_enabled",False)); f.addRow(self.chat); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.save); b.rejected.connect(self.reject); f.addRow(b)
 def save(self):
  p=self.provider.currentText(); keys=dict(self.pet.config.get("api_keys",{})); keys[p]=self.key.text().strip(); self.pet.config.update({"api_keys":keys,"provider":p,"ai_chat_enabled":self.chat.isChecked()}); self.pet.save(); self.accept()

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
  try:c=json.loads(CONFIG.read_text(encoding="utf-8")); d=cfg_default(); d.update(c); return d
  except Exception:return cfg_default()
 def save(self): CONFIG.write_text(json.dumps(self.config,ensure_ascii=False,indent=2),encoding="utf-8")
 def update(self,values): self.config.update(values); self.save(); self.apply(); self.render()
 def apply(self):
  w=int(self.config.get("size",520)); self.resize(w,max(220,round(w*CANVAS[1]/CANVAS[0]))); self.setWindowOpacity(int(self.config.get("opacity",100))/100); flags=Qt.FramelessWindowHint|Qt.Tool|(Qt.WindowStaysOnTopHint if self.config.get("always_on_top",True) else Qt.WindowType(0)); self.setWindowFlags(flags); self.setAttribute(Qt.WA_TransparentForMouseEvents,bool(self.config.get("click_through",False))); self.show()
 def render(self):
  p=self.current
  n=self.config.get("expression","default"); role=next((k for k,v in BUILTINS.items() if v==p.name),""); folder=EXPR.get(role); ep=ASSETS/"legacy_chars"/folder/"sprites"/f"{n}.png" if folder and n!="default" else None; p=ep if ep and ep.exists() else p; pix=QPixmap(str(p)); self.label.setPixmap(pix.scaled(self.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
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
  m=QMenu(self); a=m.addAction("開啟控制面板"); a.triggered.connect(self.open_panel); mode=m.addAction("切換到 API 模式" if self.config.get("mode")=="simulation" else "切換到模擬模式"); mode.triggered.connect(lambda:self.set_mode("api" if self.config.get("mode")=="simulation" else "simulation")); k=m.addAction("API Key／AI 對話設定"); k.triggered.connect(lambda:KeyDialog(self).exec()); c=m.addAction("與角色對話"); c.triggered.connect(self.chat); m.addSeparator(); actors=m.addMenu(f"可動角色（{len(self.walkers)}/{MAX_EXTRA}）"); actors.addAction("新增正常 DeepSeek 三方向").triggered.connect(lambda:self.add_walker("deepseek")); actors.addAction("新增黑化 DeepSeek 三方向").triggered.connect(lambda:self.add_walker("deepseek_dark")); disabled=actors.addAction("Claude/Gemini/GPT：沒有 walking sprite，禁止自動行走"); disabled.setEnabled(False); actors.addAction("移除所有額外角色").triggered.connect(self.remove_walkers); m.addAction("匯入自訂角色").triggered.connect(self.import_character); m.addAction("立即掉落飯盆").triggered.connect(self.spawn_bowl); m.addAction("清除飯盆").triggered.connect(self.clear_bowl); m.addAction("切換滑鼠穿透").triggered.connect(lambda:self.update({"click_through":not self.config.get("click_through",False)})); m.addAction("回到左下角").triggered.connect(self.snap); m.addSeparator(); m.addAction("退出").triggered.connect(QApplication.quit); return m
 def open_panel(self):
  if not self.panel:self.panel=Panel(self)
  self.panel.show(); self.panel.raise_(); self.panel.activateWindow()
 def set_mode(self,mode): self.update({"mode":mode}); self.tray.showMessage(APP_NAME,"已切換到"+mode)
 def select(self,name): self.current=ASSETS/name; self.update({"character":str(self.current)}); self.render()
 def set_expression(self,name): self.update({"expression":name})
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
  provider=self.config.get("provider","DeepSeek"); key=self.config.get("api_keys",{}).get(provider,"")
  if not key: QMessageBox.warning(self,"缺少 API Key","請先開啟 API Key 管理輸入 Key。"); return
  self.worker=Worker(provider,key,None,self); self.worker.done.connect(self.api_done); self.worker.start()
 def api_done(self,ok,data):
  if ok:self.config["api_balance"]=data.get("balance"); self.config["last_event"]=f"API 查詢成功：{data.get('balance')}（{data.get('source','')}）"; self.add_log(self.config["last_event"]); self.save(); QMessageBox.information(self,"API 查詢成功",self.config["last_event"])
  else: QMessageBox.warning(self,"API 查詢失敗",data.get("error","未知錯誤"))
 def chat(self):
  if not self.config.get("ai_chat_enabled",False): QMessageBox.information(self,"角色對話",random.choice(LINES)); return
  p=self.config.get("provider","DeepSeek"); key=self.config.get("api_keys",{}).get(p,"")
  if not key: QMessageBox.information(self,"角色對話",random.choice(LINES)); return
  self.worker=Worker(p,key,"請用一句繁體中文可愛地回應桌面主人。",self); self.worker.done.connect(lambda ok,d:QMessageBox.information(self,"角色對話",d.get("message",random.choice(LINES)) if ok else random.choice(LINES))); self.worker.start()

def main():
 os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING","1"); os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY","PassThrough"); app=QApplication(sys.argv); app.setApplicationName(APP_NAME); pet=Pet(); pet.snap(); return app.exec()
if __name__=="__main__":sys.exit(main())

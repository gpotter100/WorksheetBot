
import streamlit as st
import json
import os
from datetime import datetime
from pathlib import Path
import smtplib
from email.mime.text import MIMEText

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from fpdf import FPDF
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory

# -------------------------------
# 1. Model Setup
# -------------------------------
llm = ChatOpenAI(temperature=0)

# -------------------------------
# 2. Persistence Helpers
# -------------------------------
chat_history_store = {}

def get_session_history(session_id: str):
    filename = f"{session_id}_history.json"
    if session_id not in chat_history_store:
        history = InMemoryChatMessageHistory()
        if os.path.exists(filename):
            with open(filename, "r") as f:
                content = f.read().strip()
                if content:
                    messages = json.loads(content)
                    for msg in messages[-20:]:
                        history.add_message(msg)
        chat_history_store[session_id] = history
    return chat_history_store[session_id]

def save_session_history(session_id: str):
    filename = f"{session_id}_history.json"
    history = chat_history_store[session_id]
    serialized = []
    for m in history.messages:
        if hasattr(m, "model_dump"):
            serialized.append(m.model_dump())
        elif hasattr(m, "dict"):
            serialized.append(m.dict())
        else:
            serialized.append(m)
    with open(filename, "w") as f:
        json.dump(serialized, f, indent=2)

# -------------------------------
# 3. HTML Rendering
# -------------------------------

def html_template(title, instructions, sections, tips, today, child):
    css = """
    <style>
      body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #ffffff; }
      .sheet { border: 6px solid #3b82f6; border-radius: 16px; padding: 16px; }
      h1 { color: #1f2937; }
      h2 { color: #2563eb; }
      .section { margin-top: 12px; padding: 10px; background: #f0f9ff; border-radius: 8px; }
      ul { list-style: none; padding-left: 0; }
      li { margin: 6px 0; }
      .footer { text-align: center; color: #6b7280; font-size: 12px; margin-top: 10px; }
    </style>
    """

    sections_html = ""
    for name, questions in sections.items():
        items = "".join([f"<li>{q}</li>" for q in questions])
        sections_html += f"<div class='section'><h2>{name}</h2><ul>{items}</ul></div>"

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>{title} — WorksheetBot</title>
      {css}
    </head>
    <body>
      <div class="sheet">
        <div>Date: {today} • Created for {child}</div>
        <h1>{title}</h1>
        <div class="section"><h2>Instructions</h2><p>{instructions}</p></div>
        {sections_html}
        <div class="section"><h2>Parent Tips</h2><p>{tips}</p></div>
        <div class="footer">WorksheetBot • Fun learning for {child}</div>
      </div>
    </body>
    </html>
    """

def render_html_worksheet(text, child, out_dir=r"C:\Users\gpott\OneDrive\Worksheets"):
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    title = f"{child}’s Worksheet"
    instructions, tips = "", ""
    sections = {}
    current_key = None

    # Parse AI output line by line
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for l in lines:
        upper = l.upper()
        if upper.startswith("TITLE"):
            title = l.split(":", 1)[-1].strip()
        elif upper.startswith("INSTRUCTIONS"):
            instructions = l.split(":", 1)[-1].strip()
        elif upper.startswith("PARENT TIPS"):
            tips = l.split(":", 1)[-1].strip()
        elif upper.startswith("PART A"):
            current_key = "Part A"
            sections[current_key] = []
        elif upper.startswith("PART B"):
            current_key = "Part B"
            sections[current_key] = []
        elif upper.startswith("PART C"):
            current_key = "Part C"
            sections[current_key] = []
        else:
            if current_key:
                cleaned = l.lstrip("-*1234567890. ").strip()
                if cleaned:
                    sections[current_key].append(cleaned)

    # Fallbacks
    if not instructions:
        instructions = "Read each question together and encourage pointing and counting."
    if not tips:
        tips = "Celebrate effort and keep sessions short and fun."

    # Ensure at least 12 questions total
    total = sum(len(v) for v in sections.values())
    while total < 12:
        sections.setdefault("Extra Practice", []).append(
            f"Practice question {total+1}: Draw and count stars or cars."
        )
        total += 1

    today = datetime.now().strftime("%A, %B %d, %Y")
    html = html_template(title, instructions, sections, tips, today, child)

    fname = f"{child.lower()}_worksheet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    path = Path(out_dir) / fname
    path.write_text(html, encoding="utf-8")
    return str(path)


# -------------------------------
# 4. Email Helper
# -------------------------------
def send_email_link(link):
    recipients = ["gpotter100@gmail.com", "meghan.smeriglio@gmail.com"]

    msg = MIMEText(f"Here is the latest worksheet link:\n{link}")
    msg["Subject"] = "New Worksheet from WorksheetBot"
    msg["From"] = "gpotter100@gmail.com"
    msg["To"] = ", ".join(recipients)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login("gpotter100@gmail.com", "wzcs qmjo wsjw yyhc")
        server.sendmail("gpotter100@gmail.com", recipients, msg.as_string())

# -------------------------------
# 5. Build Prompt
# -------------------------------
def build_prompt(child):
    if child.lower() == "landon":
        child_context = (
            "Landon, age 7, who has high functioning autism. He loves race cars, rockets, toys, and stars. "
            "Worksheets should be structured with math, word problems, and comparisons. "
            "Generate at least 12 unique questions grouped into Parts A, B, and C. "
            "Do not repeat questions. Include playful themes, icons, and parent tips."
        )
    else:
        child_context = (
            "Declan, age 5. He loves colorful worksheets with playful Disney-style energy, Pokémon creatures, and Sprunkies. "
            "Worksheets should be simpler with counting, matching, and easy add/subtract. "
            "Generate at least 12 unique questions grouped into Parts A, B, and C. "
            "Do not repeat questions. Include playful themes, icons, and parent tips."
        )

    return ChatPromptTemplate.from_messages([
        ("system",
         f"You are WorksheetBot, a helpful assistant created by Garrett and his wife. "
         f"Your job is to create fun, educational worksheets for {child_context} "
         "Always format output in labeled sections: TITLE, INSTRUCTIONS, PART A, PART B, PART C, and PARENT TIPS. "
         "Write numbered questions within each part. "
         "Keep language friendly, concise, and encouraging. "
         "Today’s date is {{today}}. Conversation so far:\n{{history}}"),
        ("human", "{question}")
    ])

def build_chain_with_history(prompt):
    chain = prompt | llm
    return RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="question",
        history_messages_key="history",
    )


# -------------------------------
# 4. Streamlit UI
# -------------------------------
st.title("WorksheetBot for Landon & Declan")

child = st.selectbox("Choose child:", ["Landon", "Declan"])
request = st.text_input("What kind of worksheet do you want?")

if st.button("Generate Worksheet"):
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = build_prompt(child)
    chain = prompt | llm
    response = chain.invoke({"question": request, "today": today})
    bot_text = response.content

    # Parse into sections
    sections = {"Part A": [], "Part B": [], "Part C": []}
    title, instructions, tips = f"{child}'s Worksheet", "", ""
    current = None
    for line in bot_text.splitlines():
        upper = line.upper()
        if upper.startswith("TITLE"):
            title = line.split(":", 1)[-1].strip()
        elif upper.startswith("INSTRUCTIONS"):
            instructions = line.split(":", 1)[-1].strip()
        elif upper.startswith("PARENT TIPS"):
            tips = line.split(":", 1)[-1].strip()
        elif upper.startswith("PART A"):
            current = "Part A"
        elif upper.startswith("PART B"):
            current = "Part B"
        elif upper.startswith("PART C"):
            current = "Part C"
        else:
            if current and line.strip():
                sections[current].append(line.lstrip("-*1234567890. ").strip())

    # Ensure at least 12 questions
    total = sum(len(v) for v in sections.values())
    while total < 12:
        sections.setdefault("Extra Practice", []).append(
            f"Practice question {total+1}: Draw and count stars or cars."
        )
        total += 1

    html = html_template(title, instructions, sections, tips, today, child)
    st.components.v1.html(html, height=800, scrolling=True)

# -------------------------------
# 4. PDF Renderer
# -------------------------------
def pdf_template(title, instructions, sections, tips, today, child):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"{title}", ln=True, align="C")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Date: {today} • Created for {child}", ln=True)

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Instructions:", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.multi_cell(0, 10, instructions)

    for name, questions in sections.items():
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, name, ln=True)
        pdf.set_font("Arial", '', 12)
        for i, q in enumerate(questions, 1):
            pdf.multi_cell(0, 10, f"{i}. {q}")

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Parent Tips:", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.multi_cell(0, 10, tips)

    return pdf.output(dest="S").encode("latin-1")



# -------------------------------
# 6. Interactive Loop
# -------------------------------
session_id = "worksheet_session"
print("WorksheetBot is ready — let's make a worksheet! (type 'quit' to exit)")
child = input("Which child are we creating this worksheet for? (Landon or Declan): ").strip() or "Landon"

prompt = build_prompt(child)
chain_with_history = build_chain_with_history(prompt)

while True:
    user_input = input("\nYou: ")
    if user_input.lower() in ["quit", "exit"]:
        break

    today = datetime.now().strftime("%A, %B %d, %Y")
    response = chain_with_history.invoke(
        {"question": user_input, "today": today},
        config={"configurable": {"session_id": session_id}}
    )

    bot_text = response.content
    html_path = render_html_worksheet(bot_text, child=child, out_dir=r"C:\Users\gpott\OneDrive\Worksheets")
    print("\nWorksheetBot:\n")
    print(bot_text)
    print(f"\nSaved worksheet to: {html_path}\n")

    # Send the OneDrive share link by email
    send_email_link("https://1drv.ms/f/c/8c332c71673d5894/Em4N7EK4KeFCn_AGbuT2nbcBKMQ5JcZvUTm5tPPV2wgItg?e=dg")
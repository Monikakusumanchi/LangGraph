# from langgraph.graph import Graph
# from langchain_groq import ChatGroq
# llm = langchain_groq(model="llama3-70b-8192")
# llm.invoke("hi how are you")
import streamlit as st
import os
import base64
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.chains import LLMMathChain, LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.utilities import WikipediaAPIWrapper
from langchain.agents.agent_types import AgentType
from langchain.agents import Tool, initialize_agent
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
from groq import Groq

load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    st.error("Groq API Key not found in .env file")
    st.stop()

st.set_page_config(page_title="Medical Bot", page_icon="👨‍🔬")
st.title("Medical Bot")
llm_text = ChatGroq(model="gemma2-9b-it", groq_api_key=groq_api_key)
llm_image = ChatGroq(model="llama-3.2-90b-vision-preview", groq_api_key=groq_api_key)

wikipedia_wrapper = WikipediaAPIWrapper()
wikipedia_tool = Tool(
    name="Wikipedia",
    func=wikipedia_wrapper.run,
    description="A tool for searching the Internet to find various information on the topics mentioned."
)
math_chain = LLMMathChain.from_llm(llm=llm_text)
calculator = Tool(
    name="Calculator",
    func=math_chain.run,
    description="A tool for solving mathematical problems. Provide only the mathematical expressions."
)

prompt = """
You are a mathematical problem-solving assistant tasked with helping users solve their questions. Arrive at the solution logically, providing a clear and step-by-step explanation. Present your response in a structured point-wise format for better understanding.
Question: {question}
Answer:
"""

prompt_template = PromptTemplate(
    input_variables=["question"],
    template=prompt
)
# Combine all the tools into a chain for text questions
chain = LLMChain(llm=llm_text, prompt=prompt_template)

reasoning_tool = Tool(
    name="Reasoning Tool",
    func=chain.run,
    description="A tool for answering logic-based and reasoning questions."
)

# Initialize the agents for text questions
assistant_agent_text = initialize_agent(
    tools=[wikipedia_tool, calculator, reasoning_tool],
    llm=llm_text,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=False,
    handle_parsing_errors=True
)

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Welcome! I am your Assistant. How can I help you today?"}
    ]

for msg in st.session_state.messages:
    if msg["role"] == "user" and "image" in msg:
        st.chat_message(msg["role"]).write(msg['content'])
        st.image(msg["image"], caption='Uploaded Image', use_column_width=True)
    else:
        st.chat_message(msg["role"]).write(msg['content'])

st.sidebar.header("Navigation")
if st.sidebar.button("Text Question"):
    st.session_state["section"] = "text"
if st.sidebar.button("Image Question"):
    st.session_state["section"] = "image"

if "section" not in st.session_state:
    st.session_state["section"] = "text"

def clean_response(response):
    if "```" in response:
        response = response.split("```")[1].strip()
    return response

if st.session_state["section"] == "text":
    st.header("Text Question")
    st.write("Please enter your question below, and I will provide a detailed description of the problem and suggest a solution for it.")
    question = st.text_area("Your Question:")
    if st.button("Get Answer"):
        if question:
            with st.spinner("Generating response..."):
                st.session_state.messages.append({"role": "user", "content": question})
                st.chat_message("user").write(question)

                st_cb = StreamlitCallbackHandler(st.container(), expand_new_thoughts=False)
                try:
                    response = assistant_agent_text.run(st.session_state.messages, callbacks=[st_cb])
                    cleaned_response = clean_response(response)
                    st.session_state.messages.append({'role': 'assistant', "content": cleaned_response})
                    st.write('### Response:')
                    st.success(cleaned_response)
                except ValueError as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.warning("Please enter a question to get an answer.")

elif st.session_state["section"] == "image":
    st.header("Image Question")
    st.write("Please enter your question below and upload the medical image. I will provide a detailed description of the problem and suggest a solution for it.")
    question = st.text_area("Your Question:", "Example: What is the patient suffering from?")
    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])

    if st.button("Get Answer"):
        if question and uploaded_file is not None:
            with st.spinner("Generating response..."):
                image_data = uploaded_file.read()
                image_data_url = f"data:image/jpeg;base64,{base64.b64encode(image_data).decode()}"
                st.session_state.messages.append({"role": "user", "content": question, "image": image_data})
                st.chat_message("user").write(question)
                st.image(image_data, caption='Uploaded Image', use_column_width=True)

                client = Groq()

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": question
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data_url
                                }
                            }
                        ]
                    }
                ]
                try:
                    completion = client.chat.completions.create(
                        model="llama-3.2-90b-vision-preview",
                        messages=messages,
                        temperature=1,
                        max_tokens=1024,
                        top_p=1,
                        stream=False,
                        stop=None,
                    )
                    response = completion.choices[0].message.content
                    cleaned_response = clean_response(response)
                    st.session_state.messages.append({'role': 'assistant', "content": cleaned_response})
                    st.write('### Response:')
                    st.success(cleaned_response)
                except ValueError as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.warning("Please enter a question and upload an image to get an answer.")

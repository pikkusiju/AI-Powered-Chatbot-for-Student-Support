import google.generativeai as genai

genai.configure(api_key="AQ.Ab8RN6KpDFEaQ2BrTWrMtrHaxZnWDuhxz2Stgr6z4n8rN1Qc7A")

print("Available Models:\n")

for model in genai.list_models():
    if "generateContent" in model.supported_generation_methods:
        print(model.name)
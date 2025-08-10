from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Union
import os
import uuid
import aiofiles
import json

from task_engine import run_python_code
from gemini import parse_question_with_llm, answer_with_data

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api")
async def analyze(
    questions_file: UploadFile = File(..., description="Must be named questions.txt"),
    other_files:  list[UploadFile] = File(default=None, description="Optional extra files")
):
    # ✅ Create unique folder
    request_id = str(uuid.uuid4())
    request_folder = os.path.join(UPLOAD_DIR, request_id)
    os.makedirs(request_folder, exist_ok=True)

    saved_files = {}

    # ✅ Save required questions.txt
    if questions_file.filename.lower() != "questions.txt":
        return JSONResponse(
            {"message": "The required file must be named 'questions.txt'"},
            status_code=400
        )

    q_path = os.path.join(request_folder, questions_file.filename)
    async with aiofiles.open(q_path, "wb") as f:
        await f.write(await questions_file.read())
    saved_files["questions.txt"] = q_path

    async with aiofiles.open(q_path, "r") as f:
        question_text = await f.read()

    if not question_text.strip():
        return JSONResponse(
            {"message": "questions.txt is empty"},
            status_code=400
        )
    if other_files:
        for file in other_files:
            file_path = os.path.join(request_folder, file.filename)
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(await file.read())
            saved_files[file.filename] = file_path

    response = await parse_question_with_llm(
        question_text=question_text,
        uploaded_files=saved_files,
        folder=request_folder
    )
    print(response)

    execution_result = await run_python_code(response["code"], response["libraries"], folder=request_folder)
    print(execution_result)

    count = 0
    while execution_result["code"] == 0 and count < 3:
        print(f"Error occurred while scrapping x{count}")
        new_question_text = str(question_text) + "previous time this error occurred" + str(execution_result["output"])
        response = await parse_question_with_llm(
            question_text=new_question_text,
            uploaded_files=saved_files,
            folder=request_folder
        )
        print(response)
        execution_result = await run_python_code(response["code"], response["libraries"], folder=request_folder)
        print(execution_result)
        count += 1

    if execution_result["code"] != 1:
        return JSONResponse({"message": "error occurred while scrapping."})

    gpt_ans = await answer_with_data(response["questions"], folder=request_folder)
    print(gpt_ans)

    try:
        final_result = await run_python_code(gpt_ans["code"], gpt_ans["libraries"], folder=request_folder)
    except Exception:
        gpt_ans = await answer_with_data(response["questions"] + "Please follow the json structure", folder=request_folder)
        print("Retry after wrong JSON format", gpt_ans)
        final_result = await run_python_code(gpt_ans["code"], gpt_ans["libraries"], folder=request_folder)

    count = 0
    json_str = 1
    while final_result["code"] == 0 and count < 3:
        print(f"Error occurred while executing code x{count}")
        new_question_text = str(response["questions"]) + "previous time this error occurred" + str(final_result["output"])
        if json_str == 0:
            new_question_text += "follow the structure {'code': '', 'libraries': ''}"

        gpt_ans = await answer_with_data(new_question_text, folder=request_folder)
        print(gpt_ans)

        try:
            json_str = 0
            final_result = await run_python_code(gpt_ans["code"], gpt_ans["libraries"], folder=request_folder)
            json_str = 1
        except Exception as e:
            print(f"Exception occurred: {e}")
            count -= 1

        print(final_result)
        count += 1

    if final_result["code"] != 1:
        result_path = os.path.join(request_folder, "result.json")
        with open(result_path, "r") as f:
            return JSONResponse(content=json.load(f))

    result_path = os.path.join(request_folder, "result.json")
    with open(result_path, "r") as f:
        try:
            return JSONResponse(content=json.load(f))
        except Exception as e:
            return JSONResponse({"message": f"Error occurred while processing result.json: {e}"})

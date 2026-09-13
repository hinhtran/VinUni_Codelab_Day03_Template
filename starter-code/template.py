"""
Lab #3: Baseline Chatbot vs ReAct Agent
Hoàn thành bài Lab.
"""

import json

from tools import (
    TOOL_DEFINITIONS,
    TOOL_MAP,
    get_flight_info,
    get_weather_forecast,
)


SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh hỗ trợ khách hàng Vingroup.

Bạn chỉ sử dụng các công cụ được đăng ký trong Tool Registry.

Quy trình:
Thought -> Action -> Observation -> lặp lại nếu cần -> Final Answer.
"""


# ============================================================
# 1. BASELINE CHATBOT
# ============================================================

class ChatbotBaseline:
    """
    Baseline LLM Chatbot.
    Không sử dụng ReAct Loop và không sử dụng Tools.
    """

    def query(self, user_input: str) -> dict:
        answer = (
            f"[Chatbot Baseline] Trả lời cho: {user_input}"
        )

        return {
            "status": "success",
            "answer": answer,
            "tool_calls": []
        }


# ============================================================
# 2. REACT AGENT
# ============================================================

class ReActAgent:
    """
    ReAct Agent sử dụng vòng lặp:

    Thought
        ↓
    Action
        ↓
    Observation
        ↓
    Thought / Final Answer
    """

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace = []

    # --------------------------------------------------------
    # Detect flight request
    # --------------------------------------------------------

    def _needs_flight(self, text: str) -> bool:
        """
        Chỉ nhận diện các câu hỏi thực sự liên quan
        đến việc tìm/tra cứu chuyến bay.

        Không dùng từ "vé" đơn thuần vì câu FAQ:
        "Chính sách đổi trả vé máy bay Vinpearl..."
        cũng có chữ "vé".
        """

        return (
            "chuyến bay" in text
            or "tìm vé" in text
            or "giá vé" in text
            or "flight" in text
        )

    # --------------------------------------------------------
    # Detect weather request
    # --------------------------------------------------------

    def _needs_weather(self, text: str) -> bool:
        return (
            "thời tiết" in text
            or "weather" in text
        )

    # --------------------------------------------------------
    # Extract destination
    # --------------------------------------------------------

    def _get_destination(self, text: str) -> str:
        if "dad" in text or "đà nẵng" in text:
            return "DAD"

        return "SGN"

    # --------------------------------------------------------
    # Extract weather city
    # --------------------------------------------------------

    def _get_weather_city(self, text: str) -> str:
        if "dad" in text or "đà nẵng" in text:
            return "DAD"

        return "SGN"

    # --------------------------------------------------------
    # Run ReAct Agent
    # --------------------------------------------------------

    def run(self, user_input: str) -> dict:

        # Reset trace cho mỗi request
        self.trace = []

        text = user_input.lower()

        needs_flight = self._needs_flight(text)
        needs_weather = self._needs_weather(text)

        flight_result = None
        weather_result = None

        # ====================================================
        # ITERATION 1 / FAQ
        # ====================================================

        if not needs_flight and not needs_weather:

            answer = (
                "Vinpearl có chính sách đổi trả vé tùy theo "
                "điều kiện của từng loại vé và kênh đặt vé. "
                "Vui lòng kiểm tra điều kiện vé cụ thể trước "
                "khi đổi hoặc trả."
            )

            self.trace.append({
                "iteration": 1,
                "thought": (
                    "Câu hỏi là FAQ và không cần sử dụng tool."
                ),
                "final_answer": answer
            })

            return {
                "status": "completed",
                "iterations": 1,
                "trace": self.trace,
                "answer": answer
            }

        # ====================================================
        # ITERATION 1 - FLIGHT
        # ====================================================

        if needs_flight:

            destination = self._get_destination(text)

            # Nếu hỏi DAD thì dùng 1.5 triệu.
            # Nếu hỏi SGN thì dùng 2 triệu.
            if destination == "DAD":
                max_price = 1_500_000
            else:
                max_price = 2_000_000

            action = {
                "name": "get_flight_info",
                "args": {
                    "origin": "HAN",
                    "destination": destination,
                    "max_price": max_price
                }
            }

            self.trace.append({
                "iteration": 1,
                "thought": (
                    "Tôi cần tra cứu thông tin chuyến bay "
                    "phù hợp với yêu cầu của khách hàng."
                ),
                "action": action
            })

            tool = TOOL_MAP[action["name"]]

            flight_result = tool(**action["args"])

            self.trace[-1]["observation"] = flight_result

        # ====================================================
        # ITERATION 2 - WEATHER
        # ====================================================

        if needs_weather:

            city_code = self._get_weather_city(text)

            action = {
                "name": "get_weather_forecast",
                "args": {
                    "city_code": city_code
                }
            }

            iteration = 2 if needs_flight else 1

            self.trace.append({
                "iteration": iteration,
                "thought": (
                    "Tôi cần tra cứu thêm thông tin thời tiết "
                    "để trả lời đầy đủ yêu cầu."
                ),
                "action": action
            })

            tool = TOOL_MAP[action["name"]]

            weather_result = tool(**action["args"])

            self.trace[-1]["observation"] = weather_result

        # ====================================================
        # FINAL ANSWER
        # ====================================================

        answer_parts = []

        # ----------------------------------------------------
        # Flight answer
        # ----------------------------------------------------

        if flight_result is not None:

            answer_parts.append(
                "Thông tin chuyến bay:"
            )

            if flight_result:

                for flight in flight_result:

                    answer_parts.append(
                        f'- {flight["airline"]} '
                        f'({flight["flight_number"]}): '
                        f'{flight["departure_time"]} - '
                        f'{flight["price_vnd"]:,} VND'
                    )

            else:

                answer_parts.append(
                    "- Không tìm thấy chuyến bay phù hợp."
                )

        # ----------------------------------------------------
        # Weather answer
        # ----------------------------------------------------

        if weather_result is not None:

            answer_parts.append("")

            answer_parts.append(
                "Thông tin thời tiết:"
            )

            if "error" in weather_result:

                answer_parts.append(
                    f'- Lỗi: {weather_result["error"]}'
                )

            else:

                answer_parts.append(
                    f'- Thành phố: '
                    f'{weather_result["city"]}'
                )

                answer_parts.append(
                    f'- Nhiệt độ: '
                    f'{weather_result["temperature_c"]}°C'
                )

                answer_parts.append(
                    f'- Điều kiện: '
                    f'{weather_result["condition"]}'
                )

                answer_parts.append(
                    f'- Gợi ý: '
                    f'{weather_result["recommendation"]}'
                )

        answer = "\n".join(answer_parts)

        # ====================================================
        # FINAL TRACE
        # ====================================================

        if needs_flight and needs_weather:

            # Multi-step:
            # 1. Flight
            # 2. Weather
            # 3. Final Answer

            self.trace.append({
                "iteration": 3,
                "thought": (
                    "Đã có đủ dữ liệu từ các tool. "
                    "Tôi sẽ tổng hợp câu trả lời cuối."
                ),
                "final_answer": answer
            })

            iterations = 3

        else:

            # Single-step:
            # Tool → Observation → Final Answer

            self.trace[-1]["final_answer"] = answer

            iterations = 1

        # ====================================================
        # MAX ITERATION SAFEGUARD
        # ====================================================

        if self.max_iterations < iterations:

            return {
                "status": "max_iterations_reached",
                "iterations": self.max_iterations,
                "trace": self.trace[:self.max_iterations],
                "answer": answer
            }

        # ====================================================
        # NORMAL COMPLETION
        # ====================================================

        return {
            "status": "completed",
            "iterations": iterations,
            "trace": self.trace,
            "answer": answer
        }


# ============================================================
# 3. MAIN
# ============================================================

def main():

    user_query = (
        "Tìm cho tôi chuyến bay từ HAN đi SGN dưới 2 triệu, "
        "rồi cho biết thời tiết SGN nên mặc gì?"
    )

    # --------------------------------------------------------
    # Baseline
    # --------------------------------------------------------

    print("=== RUNNING CHATBOT BASELINE ===")

    chatbot = ChatbotBaseline()

    baseline_result = chatbot.query(user_query)

    print(
        json.dumps(
            baseline_result,
            indent=2,
            ensure_ascii=False
        )
    )

    # --------------------------------------------------------
    # ReAct Agent
    # --------------------------------------------------------

    print("\n=== RUNNING REACT AGENT ===")

    agent = ReActAgent(max_iterations=5)

    result = agent.run(user_query)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
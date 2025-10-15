import pytest
from unittest.mock import AsyncMock, patch
from jobs.task import send_whatsapp_message

valid_msg = {
    "to": "+1234567890",
    "type": "text",
    "text": {
        "body": "Hello!"
    }
}

invalid_msg = {
    "bad": "input"
}


@patch("jobs.task.WhatsappSendMessageService")
def test_send_whatsapp_message_success(mock_service):
    mock_instance = mock_service.return_value
    mock_instance.send_whatsapp_message = AsyncMock(return_value="ok")

    result = send_whatsapp_message.delay(valid_msg)

    assert result.get(timeout=3) == "ok"
    mock_instance.send_whatsapp_message.assert_awaited_once()


@patch("app.tasks.WhatsappSendMessageService")
def test_send_whatsapp_message_invalid_input(mock_service, caplog):
    result = send_whatsapp_message.delay(invalid_msg)

    assert result.get(timeout=3) is None
    assert "Invalid MessageRequest input" in caplog.text
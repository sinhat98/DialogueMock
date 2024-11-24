# src/modules/reservation/manager.py

from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
from src.utils import get_custom_logger

logger = get_custom_logger(__name__)

class Reservation:
    """予約情報を表すデータクラス"""
    def __init__(self, name: str, date: str, time: str, num_people: int,
                 reservation_id: Optional[str] = None):
        self.reservation_id = reservation_id or self._generate_id()
        self.name = name
        self.date = date
        self.time = time
        self.num_people = num_people
        self.status = "active"  # active, cancelled
        self.created_at = datetime.now()

    def _generate_id(self) -> str:
        """予約IDを生成"""
        return datetime.now().strftime("%Y%m%d%H%M%S")

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "名前": self.name,
            "日付": self.date,
            "時間": self.time,
            "人数": str(self.num_people),
            "予約ID": self.reservation_id,
            "状態": self.status
        }

class ReservationManager:
    def __init__(self):
        """
        予約管理システムの初期化
        """
        self.reservations: Dict[str, Reservation] = {}  # 予約ID -> Reservation
        self.max_seats = 50  # 最大座席数
        self.business_hours = {
            "start": time(11, 0),  # 11:00
            "end": time(22, 0)     # 22:00
        }
        self.holiday = "水曜日"  # 定休日

    def create_reservation(self, name: str, date: str, time_str: str, 
                         num_people: int) -> Dict[str, str]:
        """
        新規予約を作成
        Returns:
            Dict[str, str]: 処理結果
                - status: "SUCCESS", "HOLIDAY", "FULL", "INVALID_TIME"
                - message: 結果メッセージ
                - reservation: 予約情報（成功時のみ）
        """
        # 定休日チェック
        if self._is_holiday(date):
            logger.info(f"Attempted to make reservation on holiday: {date}")
            return {
                "status": "HOLIDAY",
                "message": "定休日です"
            }

        # 営業時間チェック
        if not self._is_valid_time(time_str):
            logger.info(f"Attempted to make reservation outside business hours: {time_str}")
            return {
                "status": "INVALID_TIME",
                "message": "営業時間外です"
            }

        # 空席チェック
        if not self._has_available_seats(date, time_str, num_people):
            logger.info(f"No available seats for {num_people} people at {date} {time_str}")
            return {
                "status": "FULL",
                "message": "満席です"
            }

        # 予約作成
        reservation = Reservation(name, date, time_str, num_people)
        self.reservations[reservation.reservation_id] = reservation
        
        logger.info(f"Created reservation: {reservation.to_dict()}")
        return {
            "status": "SUCCESS",
            "message": "予約が完了しました",
            "reservation": reservation.to_dict()
        }

    def find_reservation(self, name: str, date: Optional[str] = None) -> Optional[Dict]:
        """
        予約を検索
        Args:
            name (str): 予約者名
            date (Optional[str]): 日付（オプション）
        Returns:
            Optional[Dict]: 予約情報
        """
        for reservation in self.reservations.values():
            if reservation.status != "active":
                continue

            if date:
                if reservation.name == name and reservation.date == date:
                    logger.info(f"Found reservation for {name} on {date}")
                    return reservation.to_dict()
            else:
                if reservation.name == name:
                    logger.info(f"Found reservation for {name}")
                    return reservation.to_dict()

        logger.info(f"No reservation found for {name}" + (f" on {date}" if date else ""))
        return None

    def cancel_reservation(self, name: str, date: Optional[str] = None) -> Dict[str, str]:
        """
        予約をキャンセル
        Returns:
            Dict[str, str]: 処理結果
        """
        reservation_found = False
        for reservation in self.reservations.values():
            if reservation.status != "active":
                continue

            if date:
                if reservation.name == name and reservation.date == date:
                    reservation_found = True
                    reservation.status = "cancelled"
            else:
                if reservation.name == name:
                    reservation_found = True
                    reservation.status = "cancelled"

        if reservation_found:
            logger.info(f"Cancelled reservation for {name}")
            return {
                "status": "SUCCESS",
                "message": "予約をキャンセルしました"
            }
        else:
            logger.info(f"No reservation found to cancel for {name}")
            return {
                "status": "NOT_FOUND",
                "message": "予約が見つかりません"
            }

    def _is_holiday(self, date_str: str) -> bool:
        """定休日かどうかをチェック"""
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            return date.strftime("%A") == self.holiday
        except ValueError:
            logger.error(f"Invalid date format: {date_str}")
            return False

    def _is_valid_time(self, time_str: str) -> bool:
        """有効な予約時間かどうかをチェック"""
        try:
            reservation_time = datetime.strptime(time_str, "%H:%M").time()
            return (self.business_hours["start"] <= reservation_time <= 
                   self.business_hours["end"])
        except ValueError:
            logger.error(f"Invalid time format: {time_str}")
            return False

    def _has_available_seats(self, date: str, time_str: str, num_people: int) -> bool:
        """指定の日時で利用可能な座席があるかチェック"""
        occupied_seats = 0
        for reservation in self.reservations.values():
            if (reservation.status == "active" and 
                reservation.date == date and 
                reservation.time == time_str):
                occupied_seats += reservation.num_people

        return (occupied_seats + num_people) <= self.max_seats

    def get_available_times(self, date: str) -> List[str]:
        """
        指定日の予約可能な時間帯を取得
        Returns:
            List[str]: 予約可能な時間帯のリスト
        """
        if self._is_holiday(date):
            return []

        available_times = []
        current_time = self.business_hours["start"]
        
        while current_time <= self.business_hours["end"]:
            time_str = current_time.strftime("%H:%M")
            if self._has_available_seats(date, time_str, 1):  # 1名分でも空きがあるか
                available_times.append(time_str)
            current_time = (datetime.combine(datetime.today(), current_time) + 
                          timedelta(minutes=30)).time()

        return available_times
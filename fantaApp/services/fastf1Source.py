import fastf1
import pandas as pd
import logging

logging.getLogger("fastf1").setLevel(logging.CRITICAL)


def get_sprint_qualifying_result(season: int, round: int):

    ss = fastf1.get_session(season, round, "Sprint Qualifying")
    ss.load(telemetry=False)
    
    #Index(['DriverNumber', 'BroadcastName', 'Abbreviation', 'DriverId', 'TeamName',
    #       'TeamColor', 'TeamId', 'FirstName', 'LastName', 'FullName',
    #       'HeadshotUrl', 'CountryCode', 'Position', 'ClassifiedPosition',
    #       'GridPosition', 'Q1', 'Q2', 'Q3', 'Time', 'Status', 'Points', 'Laps'],
    #      dtype='object')

    df = (
        ss.results[
            [
                "DriverNumber",
                "Abbreviation",
                "FirstName",
                "LastName",
                "DriverId",
                "Position",
                "Q1",
                "Q2",
                "Q3",
            ]
        ]
        .rename(
            columns={
                "DriverNumber": "number",
                "Abbreviation": "short_name",
                "FirstName": "first_name",
                "LastName": "last_name",
                "DriverId": "fastf1_driver_id",
                "Position": "position",
                "Q1": "q1_time",
                "Q2": "q2_time",
                "Q3": "q3_time",
            }
        )
    )

    df["position"] = pd.to_numeric(df["position"], errors="coerce").astype("Int64")
    df["number"] = pd.to_numeric(df["number"], errors="coerce").astype("Int64")
    df["short_name"] = df["short_name"].astype("string")
    df["first_name"] = df["first_name"].astype("string")
    df["last_name"] = df["last_name"].astype("string")
    df["fastf1_driver_id"] = df["fastf1_driver_id"].astype("string")
    
    df["q1_time"] = df["q1_time"].apply(lambda td: str(td) if pd.notna(td) else None)
    df["q2_time"] = df["q2_time"].apply(lambda td: str(td) if pd.notna(td) else None)
    df["q3_time"] = df["q3_time"].apply(lambda td: str(td) if pd.notna(td) else None)
    
    quali_result = df.to_dict(orient="records")
    
    return quali_result
import traceback
from .. import write_error


def program_error(
    e: Exception,
    error_file: str,
    parameter: list
) -> dict:
    error_info = traceback.format_exc()
    track_id = write_error(
        error_file=error_file,
        error_params=parameter,
        error_name=str(type(e).__name__),
        error_info=error_info
    )
    return {
        'status': 'error',
        'message': 'PROGRAM ERROR',
        'error': f'{str(type(e).__name__)}',
        'track_id': f'{track_id}'
    }


def ship_id_sort(
    ship_list:list
):
    res_list = []
    for tier_index in [10,9,8,7,6,5]:
        for type_index in ['AirCarrier', 'Battleship', 'Cruiser', 'Destroyer', 'Submarine']:
            for ship_info in ship_list:
                if ship_info[1] == tier_index and ship_info[2] == type_index:
                    res_list .append(ship_info)
    return res_list

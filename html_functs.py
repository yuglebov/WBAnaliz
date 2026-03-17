"""
Модуль для обработки данных отчётов Wildberries.

Функции:
- generate_report: преобразует сырые данные API в агрегированную статистику по товарам.
- save_report_data: сохраняет рассчитанные метрики в базу данных.
- is_float: проверяет, можно ли строку преобразовать в число.
"""

from models import db, ReportData


def is_float(s):
    """Проверяет, можно ли преобразовать строку в число."""
    try:
        float(s)
        return True
    except ValueError:
        return False

# Generate report
def generate_report(data, cost_prices): # pylint: disable=too-many-branches
    """
    Генерирует отчёт по продажам на основе данных от Wildberries API.

    :param data: список операций от API Wildberries.
    :param cost_prices: словарь {артикул: себестоимость}.
    :return: агрегированные данные по каждому товару.
    """
    report_data = {}
    tax_rate = 0.06

    for item in data:
        sa_name = item.get('sa_name')
        if not sa_name or sa_name not in cost_prices:
            continue # Пропускаем товары без себестоимости
        # Инициализация записи, если ещё не существует
        if sa_name not in report_data:
            report_data[sa_name] = {
                'logistics_count': 0,
                'logistics_sum': 0,
                'return_logistics_count': 0,
                'return_logistics_sum': 0,
                'sales_count': 0,
                'payout_sum': 0,
                'retail_price_sum': 0,
                'cost_price_total': 0,
                'custom_calculation': 0,
                'storage_fee': 0,
                'penalty': 0,
                'deduction': 0,
                'ad': 0,
                'other': 0,
                'custom_payout': 0,
                'return_sum': 0,
            }

        if item['supplier_oper_name'] == 'Логистика':
            if item['bonus_type_name'] == 'К клиенту при продаже':
                report_data[sa_name]['logistics_count'] += item['delivery_amount'] or 0
                report_data[sa_name]['logistics_sum'] += item['delivery_rub'] or 0
            else:
                if item['return_amount'] == 0:
                    report_data[sa_name]['logistics_count'] += item['delivery_amount'] or 0
                    report_data[sa_name]['logistics_sum'] += item['delivery_rub'] or 0
                else:
                    report_data[sa_name]['return_logistics_count'] += item['return_amount'] or 0
                    report_data[sa_name]['return_logistics_sum'] += item['delivery_rub'] or 0

        elif item['supplier_oper_name'] == 'Продажа':
            retail_price_with_tax = item['retail_price'] * tax_rate

            report_data[sa_name]['sales_count'] += item['quantity'] or 0
            report_data[sa_name]['payout_sum'] += item['ppvz_for_pay'] or 0
            report_data[sa_name]['retail_price_sum'] += retail_price_with_tax or 0

            # Рассчитываем себестоимость
            cost_price = cost_prices.get(sa_name, 0)
            report_data[sa_name]['cost_price_total'] += cost_price * (item['quantity'] or 0)

        elif item['supplier_oper_name'] == 'Возврат':
            report_data[sa_name]['return_sum'] += item['ppvz_for_pay'] or 0

        elif item['supplier_oper_name'] == 'Хранение':
            report_data[sa_name]['storage_fee'] += item['storage_fee']

        elif item['supplier_oper_name'] == 'Штраф':
            report_data[sa_name]['penalty'] += item['penalty']

        elif item['supplier_oper_name'] == 'Удержание':
            if item['bonus_type_name'] == 'Оказание услуг «ВБ.Продвижение»':
                report_data[sa_name]['ad'] += item['deduction'] or 0
            else:
                report_data[sa_name]['deduction'] += item['deduction'] or 0

        elif item['supplier_oper_name'] == ('Возмещение издержек по перевозке'
                                            '/по складским операциям с товаром'):
            report_data[sa_name]['other'] += item['rebill_logistic_cost'] or 0

    return report_data

def save_report_data(report_data, cost_prices, user_id):
    """
    Сохраняет данные отчёта в базу данных.

    :param report_data: агрегированные данные по товарам.
    :param cost_prices: словарь себестоимостей.
    :param user_id: ID пользователя.
    """

    # Delete old data
    ReportData.query.filter(ReportData.user_id == user_id).delete()
    db.session.commit()
    for sa_name, stats in report_data.items():
        cost_price_per_unit = cost_prices.get(sa_name, 0)
        buyout_percentage = (
            (stats['sales_count'] /
            (stats['logistics_count'] +
            stats['return_logistics_count'])) * 100
            if stats['logistics_count'] > 0 else 0
        )
        custom_calculation = (
            stats['payout_sum'] -
            stats['logistics_sum'] -
            stats['return_logistics_sum'] -
            stats['retail_price_sum'] -
            stats['cost_price_total'] -
            stats['storage_fee'] -
            stats['penalty'] -
            stats['ad'] -
            stats['deduction'] +
            stats['other'] -
            stats['return_sum']
        )

        custom_payout = (
            stats['payout_sum'] -
            stats['logistics_sum'] -
            stats['return_logistics_sum'] -
            stats['storage_fee'] -
            stats['penalty'] -
            stats['ad'] -
            stats['deduction'] +
            stats['other'] -
            stats['return_sum']
        )

        roi = ((custom_calculation / (stats['sales_count'] * cost_price_per_unit)) * 100
            if stats['sales_count'] > 0 and cost_price_per_unit > 0 else 0
        )
        # Insert new data
        report = ReportData(
            sa_name=sa_name,
            logistics_count=stats['logistics_count'],
            logistics_sum=stats['logistics_sum'],
            return_logistics_count=stats['return_logistics_count'],
            return_logistics_sum=stats['return_logistics_sum'],
            sales_count=stats['sales_count'],
            payout_sum=stats['payout_sum'],
            retail_price_sum=stats['retail_price_sum'],
            cost_price_total=stats['cost_price_total'],
            storage_fee=stats['storage_fee'],
            penalty=stats['penalty'],
            ad=stats['ad'],
            deduction=stats['deduction'],
            other=stats['other'],
            return_sum=stats['return_sum'],
            custom_calculation=custom_calculation,
            custom_payout=custom_payout,
            roi=roi,
            buyout_percentage=buyout_percentage,
            user_id=user_id
        )
        db.session.add(report)
    db.session.commit()

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
from datetime import datetime


async def create_graph(data):
    months, user_counts = zip(*data)

    # Вычисление общего количества пользователей
    total_users = list()
    cumulative_sum = 0
    for count in user_counts:
        cumulative_sum += count
        total_users.append(cumulative_sum)

    fig, ax = plt.subplots(figsize=(15, 8))

    # Установка сетки за столбами
    ax.set_axisbelow(True)
    ax.grid(True, which='both', axis='both')

    # Форматирование меток оси X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    # Определение цветовой палитры
    cmap = plt.get_cmap('tab20')
    bar_width = 20 / len(months)  # Адаптивная ширина столбцов

    # Создание гистограммы с разными цветами
    for i, (month, user_count) in enumerate(zip(months, user_counts)):
        ax.bar(month, user_count, color=cmap(i / len(months)), width=bar_width)

    # Установка подписей оси X по центру под столбами
    ax.set_xticks(months)
    ax.set_xticklabels([month.strftime('%Y-%m') for month in months], rotation=0, ha='center')

    plt.xlabel('Месяц')
    plt.ylabel('Количество новых пользователей')
    plt.title('Активность регистрации пользователей по месяцам')

    # Добавление аннотаций
    for month, user_count, total in zip(months, user_counts, total_users):
        ax.annotate(f'{user_count}', xy=(month, user_count), xytext=(0, 5), textcoords='offset points', ha='center')
        ax.annotate(f'Всего: {total}', xy=(month, user_count), xytext=(0, 20), textcoords='offset points', ha='center', fontsize=8, color='gray')

    # Добавление линии общего количества пользователей
    ax2 = ax.twinx()
    ax2.plot(months, total_users, color='red', linestyle='--', marker='o', label='Общее количество пользователей')
    ax2.set_ylabel('Общее количество пользователей')
    ax2.legend(loc='upper left')

    # Сохранение изображения в память
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    return img_data

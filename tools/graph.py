import io

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


async def create_graph(data):
    months, user_counts = zip(*data)
    fig, ax = plt.subplots(figsize=(15, 8))

    # Создание дополнительного пространства слева для текста
    fig.subplots_adjust(left=0.3)

    # Установка сетки за столбами
    ax.set_axisbelow(True)
    ax.grid(True, which='both', axis='both')

    # Форматирование меток оси X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    # Определение цветовой палитры
    cmap = plt.get_cmap('tab20')
    bar_width = 0.8  # Ширина столбцов

    # Создание гистограммы с разными цветами
    for i, (month, user_count) in enumerate(zip(months, user_counts)):
        ax.bar(month, user_count, color=cmap(i / len(months)), width=bar_width, label=month.strftime('%Y-%m'))

    # Установка подписей оси X по центру под столбами
    ax.set_xticks(months)
    ax.set_xticklabels([month.strftime('%Y-%m') for month in months], rotation=0, ha='center')

    plt.xlabel('Месяц')
    plt.ylabel('Количество новых пользователей')
    plt.title('Активность регистрации пользователей по месяцам')

    # Добавление аннотаций
    for month, user_count in zip(months, user_counts):
        ax.annotate(f'{user_count}', xy=(month, user_count), xytext=(0, 5), textcoords='offset points', ha='center')

    # Подсчет суммарного количества пользователей
    total_users = sum(user_counts)

    # Добавление текста с суммарным количеством пользователей
    plt.text(-0.5, max(user_counts) / 2, f'Суммарное количество пользователей: {total_users}', fontsize=12, va='center')

    # Добавление легенды
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), title='Месяц')

    # Сохранение изображения в память
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    return img_data

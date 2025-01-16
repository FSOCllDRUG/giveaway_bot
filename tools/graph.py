import io

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


async def create_graph(data):
    months, user_counts = zip(*data)

    # Подсчет суммарного количества пользователей
    total_users = sum(user_counts)

    fig, ax = plt.subplots(figsize=(15, 8))

    # Сдвиг графика вправо для добавления текста слева
    plt.subplots_adjust(left=0.3, right=0.9)

    # Установка сетки за столбами
    ax.set_axisbelow(True)
    ax.grid(True, which='both', axis='both')

    # Форматирование меток оси X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    # Определение цветовой палитры
    cmap = plt.get_cmap('tab20')
    bar_width = 0.5  # Ширина столбцов

    # Создание гистограммы с разными цветами
    for i, (month, user_count) in enumerate(zip(months, user_counts)):
        ax.bar(month, user_count, color=cmap(i / len(months)), width=bar_width, label=month.strftime('%Y-%m'))

    # Установка подписей оси X по центру под столбами
    ax.set_xticks(months)
    ax.set_xticklabels([month.strftime('%Y-%m') for month in months], rotation=0, ha='center')

    plt.xlabel('Месяц')
    plt.ylabel('Количество новых пользователей')
    plt.title('Активность регистрации пользователей по месяцам')

    # Добавление аннотаций в виде таблицы слева от графика
    annotation_text = f'Общее количество пользователей: {total_users}\n\n'
    for month, user_count in zip(months, user_counts):
        annotation_text += f'{month.strftime("%Y-%m")}: {user_count} пользователей\n'

    # Добавление текста с аннотациями слева
    fig.text(0.1, 0.5, annotation_text, fontsize=12, va='center', ha='left')

    # Добавление легенды
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), title='Месяц')

    # Сохранение изображения в память
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    return img_data

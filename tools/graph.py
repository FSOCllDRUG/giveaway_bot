import io

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


async def create_graph(data):
    months, user_counts = zip(*data)
    fig, ax = plt.subplots(figsize=(15, 8))

    # Сдвиг графика к правому краю
    plt.subplots_adjust(left=0.35, right=0.95)

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
    for month, user_count in zip(months, user_counts):
        ax.annotate(f'{user_count}', xy=(month, user_count), xytext=(0, 5), textcoords='offset points', ha='center')

    total_users = sum(user_counts)
    legend_text = [f'{month.strftime("%Y-%m")}: {user_count}' for
                   month, user_count in zip(months, user_counts)] + [f'Всего: {total_users}']
    ax.legend(legend_text, loc='center left', bbox_to_anchor=(-0.3, 0.5))

    # Сохранение изображения в память
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    return img_data

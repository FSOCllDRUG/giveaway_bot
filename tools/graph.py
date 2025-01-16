import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io


async def create_graph(data):
    months, user_counts = zip(*data)
    fig, ax = plt.subplots(figsize=(15, 8))

    # Установка сетки за столбами
    ax.set_axisbelow(True)
    ax.grid(True, which='both', axis='both')

    # Форматирование меток оси X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=90)

    # Определение цветовой палитры
    colors = plt.cm.get_cmap('tab20', len(months)).colors

    # Создание гистограммы с разными цветами
    for i, (month, user_count) in enumerate(zip(months, user_counts)):
        ax.bar(month, user_count, color=colors[i], width=20)

    # Установка подписей оси X по центру под столбами
    ax.set_xticks(months)
    ax.set_xticklabels([month.strftime('%Y-%m') for month in months], rotation=90, ha='center')

    plt.xlabel('Месяц')
    plt.ylabel('Количество новых пользователей')
    plt.title('Активность регистрации пользователей по месяцам')

    # Добавление аннотаций
    for month, user_count in zip(months, user_counts):
        ax.annotate(f'{user_count}', xy=(month, user_count), xytext=(0, 5), textcoords='offset points', ha='center')

    # Сохранение изображения в память
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    return img_data

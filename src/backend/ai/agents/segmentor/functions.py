from src.backend.ai.client import client
from src.backend.ai.schemas import TextSegment, AddonChapterPartsInfo
from src.backend.ai.agents.segmentor.task import cut_pieces
import numpy as np
import spacy

def format_window(segments: list[TextSegment], start: int, end: int) -> str:
    return "".join(format_segment(segments[i]) for i in range(start, end))

def format_segment(segment: TextSegment) -> str:
    return f"{segment.tag_name} {segment.original_text}\n"


nlp = spacy.load("ru_core_news_md")  # нужна модель с векторами

def can_cut_after(text: str) -> bool:
    """Резать можно только после законченной фразы."""
    text = text.strip()
    return len(text) > 2 and text.endswith((".", "!", "?", "…", "»"))


def find_best_cut(segments: list[TextSegment]) -> int:
    """Индекс, после которого смысл меняется сильнее всего."""
    vectors = [nlp(s.original_text).vector for s in segments]

    def gap(i: int) -> float:
        a, b = vectors[i], vectors[i + 1]
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return 1 - (a @ b / norm) if norm else 0.0

    candidates = [i for i in range(len(segments) - 1) if can_cut_after(segments[i].original_text)]
    return max(candidates or range(len(segments) - 1), key=gap)


def split_into_sentences(segment: TextSegment) -> list[TextSegment]:
    sentences = [s.text for s in nlp(segment.original_text).sents]
    return [TextSegment(tag_name=f"{segment.tag_name}#{k}", original_text=t, translated_text=None)
            for k, t in enumerate(sentences, 1)]


async def retrieve_chapter_texts(segments: list[TextSegment], budget: int) -> list[AddonChapterPartsInfo]:
    text = format_window(segments, 0, len(segments))

    # 1. Влезает — отдаём модели
    if await client.count_tokens(text) <= budget:
        return await cut_pieces([s.tag_name for s in segments], text)

    # 2. Один абзац не влезает — делим на предложения
    if len(segments) == 1:
        sentences = split_into_sentences(segments[0])
        if len(sentences) == 1:
            return await cut_pieces([segments[0].tag_name], text)
        return await retrieve_chapter_texts(sentences, budget)

    # 3. Режем по смысловой границе и повторяем для обеих половин
    cut = find_best_cut(segments)
    first = await retrieve_chapter_texts(segments[: cut + 1], budget)
    second = await retrieve_chapter_texts(segments[cut + 1:], budget)
    return first + second

if __name__ == "__main__":
    import asyncio

    text_segments = [TextSegment(tag_name='TEXT[1]', original_text='1', translated_text=None),
                     TextSegment(tag_name='TEXT[2]',
                                 original_text='Артур Питт попал в толпу сразу же, как только покинул офис'
                                               ' «Единства»'
                                               ' и стал переходить улицу. Остановившись на углу возле своего'
                                               ' автомобиля,'
                                               ' он прикурил сигарету. Затем открыл дверцу машины,'
                                               ' взял кейс-атташе и стал внимательно изучать толпу.'
                                               ' Их было человек пятьдесят-шестьдесят — все это'
                                               ' были местные жители: рабочие, механики, водители,'
                                               ' фермеры, домохозяйки, бакалейщики.'
                                               ' Самые обыкновенные представители среднего класса.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[3]',
                                 original_text='Питт скользнул на сидение и, взяв микрофон, встроенный в панель'
                                               ' автомобиля, вызвал старшего по званию — начальника'
                                               ' южно-американского региона. Люди уже заполнили улицу и направлялись'
                                               ' прямо к нему. Вне всякого сомнения, они опознали его по одежде,'
                                               ' соответствовавшей Т-классу — белой рубашке с галстуком, серому'
                                               ' костюму, фетровой шляпе. Атташе-кейс. Сияющие черные туфли.'
                                               ' Наконечник лучевого карандаша, торчащий из нагрудного кармана.'
                                               ' Он вытащил золотистую трубку и держал ее наготове.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[4]',
                                 original_text='—\xa0Критическое положение,\xa0— произнес он.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[5]',
                                 original_text='—\xa0Таубман слушает,\xa0— донеслось из микрофона.\xa0—'
                                               ' Где вы находитесь?\xa0— Официальный голос доносился'
                                               ' откуда-то сверху.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[6]',
                                 original_text='—\xa0Все еще в Кедровой Роще, в Алабаме. Вокруг меня собирается'
                                               ' толпа. Предполагаю, она блокировала дорогу. Похоже,'
                                               ' что весь город собрался здесь.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[7]', original_text='—\xa0Какие-то Исцелители?',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[8]',
                                 original_text='На краю тротуара молча стоял старик с крупной головой'
                                               ' и короткой стрижкой. Он был одет в широкую, свободного покроя,'
                                               ' одежду, сандалии и подпоясан узловатой веревкой.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[9]', original_text='—\xa0Он один,\xa0— ответил Питт.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[10]', original_text='—\xa0Попробуйте снять для «Вулкана-3».',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[11]', original_text='—\xa0Попытаюсь.', translated_text=None)]
    asyncio.run(retrieve_chapter_texts(text_segments, 100))

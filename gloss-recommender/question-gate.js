// 의사 질문이 표제어를 추천할 만한 내용을 담고 있는지 판정한다.
//
// - no_question: 입력이 비었거나 구두점·간투사("음", "네")·진행 멘트("다음 분",
//   "잠시만요")뿐이라 질문이 없는 경우.
// - ambiguous_question: 지시어·대용어("그거", "여기")와 범용 서술어("어떠세요",
//   "하실래요")만 있어 무엇을 묻는지 알 수 없는 경우.
//
// 임베딩 검색 점수만으로는 이런 입력을 거를 수 없다. "그거 어떠세요?"는
// "느끼시는 거는 어떠세요?"와 0.87로 매칭된다. 그래서 내용어가 하나라도 있는지를
// 어휘로 직접 본다. 데이터셋 질문과 정확히 같은 문장은 검증된 질문이므로 통과시킨다.

// 간투사·응답어. 이것만 있으면 질문이 없는 것이다.
const FILLER_TOKENS = new Set([
  '음', '음음', '으음', '흠', '흐음', '어', '어어', '아', '아아', '에', '에이', '엄', '엉',
  '네', '넵', '넹', '예', '응', '웅', '자', '저', '저기', '저기요', '그', '뭐', '아니', '글쎄',
]);

// 질문이 아닌 진행 멘트.
const NON_QUESTION_TOKENS = new Set([
  '다음', '다음분', '분', '잠시만', '잠시만요', '잠깐만', '잠깐만요', '잠시', '잠깐',
  '알겠습니다', '알겠어요', '알았어요', '알았습니다', '감사합니다', '고맙습니다',
  '수고하셨습니다', '수고하세요', '안녕히', '가세요', '계세요', '들어오세요',
]);

// 지시어·대용어·정도부사·범용 서술어. 이것만으로는 무엇을 묻는지 알 수 없다.
const VAGUE_TOKENS = new Set([
  '그거', '그게', '그건', '그걸', '그것', '그것은', '그것도', '그거는', '그거도',
  '이거', '이게', '이건', '이걸', '이것', '이것은', '이거는',
  '저거', '저게', '저건', '저걸', '저것', '저거는',
  '여기', '여기는', '여기도', '거기', '거기는', '거기도', '저기는',
  '그렇게', '이렇게', '저렇게', '그런', '이런', '저런', '그런거', '이런거', '저런거',
  '그런가', '그렇죠', '그렇지', '그렇지요', '그렇군', '그래', '그래서', '그러면', '그럼',
  '그러니까', '그런데', '근데', '그리고', '그러세', '그러세요', '그러신가',
  '어떻게', '어때', '어떠세', '어떠세요', '어떠신가', '어떠셨어', '어떠셨나', '어떤가',
  '어떻습니까', '어떡해', '어떡할까', '어떡하', '어떻', '어떤', '어느',
  '괜찮아', '괜찮으세', '괜찮죠', '괜찮습니까', '괜찮으신가', '괜찮나', '괜찮으셨어',
  '좀', '조금', '약간', '많이', '너무', '되게', '정말', '진짜', '혹시', '그냥', '제일', '가장',
  '아까', '이따', '나중에', '지금', '이제', '다시', '또', '계속', '한번', '먼저', '일단',
  '하실래', '하시겠어', '하시겠습니까', '할까', '할게', '하세', '해', '해볼까', '합시다',
  '하죠', '하시', '하셨어', '하셨나', '해도', '되나', '되세', '됐어', '됐나', '돼',
  '있어', '있으세', '있나', '있으신가', '있으셨어', '없어', '없으세', '없나',
  '맞아', '맞죠', '맞나', '맞으세', '아니에', '아니죠', '아닌가', '말이에', '말이죠',
  '말씀', '말씀이세', '말씀하셨', '무슨', '뭐가', '뭘', '뭐예', '뭔가', '무엇', '무엇이',
  '왜', '언제', '어디', '누구', '얼마나', '몇', '거', '것', '게', '건', '걸', '수',
  '선생님', '환자분', '제가', '저는', '저도',
]);

// 조사 없이 한 음절로 쓰이는 의료 내용어. 한 음절 토큰은 대부분 간투사지만 이 목록은 내용어다.
const SINGLE_SYLLABLE_CONTENT = new Set([
  '술', '약', '목', '팔', '턱', '발', '손', '열', '잠', '밤', '암', '피', '귀', '눈',
  '코', '입', '등', '배', '뼈', '살', '키', '침', '땀', '숨', '낮', '밥', '물', '변',
]);

function questionTokens(text) {
  return String(text || '')
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean);
}

// 문장 끝의 "요"는 떼고 한 번 더 본다. ("그거요", "여기요", "어떠세요")
function inSet(set, token) {
  return set.has(token) || (token.length > 1 && token.endsWith('요') && set.has(token.slice(0, -1)));
}

function isContentToken(token) {
  if (/\p{N}/u.test(token)) return true; // "10점", "3일" 같은 수치는 내용이다.
  if (inSet(FILLER_TOKENS, token) || inSet(NON_QUESTION_TOKENS, token) || inSet(VAGUE_TOKENS, token)) return false;
  if (token.length === 1) return SINGLE_SYLLABLE_CONTENT.has(token);
  return true;
}

function normalizeQuestionKey(text) {
  return questionTokens(text).join('');
}

// knownQuestions: 데이터셋 질문 문자열 배열. 정확히 같은 질문은 판정 없이 통과한다.
function analyzeQuestionContent(question, knownQuestions = []) {
  const tokens = questionTokens(question);
  const key = tokens.join('');
  if (!key) {
    return { ok: false, code: 'no_question', message: '의사 질문이 없어 표제어를 추천하지 않습니다.', tokens, contentTokens: [] };
  }
  if (knownQuestions.some(item => normalizeQuestionKey(item) === key)) {
    return { ok: true, code: 'known_question', tokens, contentTokens: tokens };
  }
  if (tokens.every(token => inSet(FILLER_TOKENS, token) || inSet(NON_QUESTION_TOKENS, token))) {
    return { ok: false, code: 'no_question', message: '의사 질문이 없어 표제어를 추천하지 않습니다.', tokens, contentTokens: [] };
  }
  const contentTokens = tokens.filter(isContentToken);
  if (!contentTokens.length) {
    return {
      ok: false,
      code: 'ambiguous_question',
      message: '질문이 무엇을 묻는지 특정되지 않아 표제어를 추천하지 않습니다. 증상·부위·시점 등을 담아 다시 질문하세요.',
      tokens,
      contentTokens,
    };
  }
  return { ok: true, code: 'ok', tokens, contentTokens };
}

module.exports = { analyzeQuestionContent, questionTokens };

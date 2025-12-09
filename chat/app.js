const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const imageInput = document.getElementById('imageInput');
const messageList = document.getElementById('messageList');
const chatScroll = document.getElementById('chatScroll');
const imagePreviewBar = document.getElementById('imagePreview');
const previewImage = document.getElementById('previewImage');
const previewName = document.getElementById('previewName');
const removeImageBtn = document.getElementById('removeImage');

let selectedImageDataUrl = null;
let selectedImageName = '';

const messages = [];
updateImagePreview();

const createMessage = (data, forcedId) => ({
  id: forcedId || `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`,
  createdAt: new Date(),
  ...data,
});

const initialMessage = createMessage({
  role: 'assistant',
  text: '안녕하세요! interio AI 비서입니다. 공간의 용도, 원하는 무드, 예산을 알려주시면 바로 맞춤형 레이아웃과 제품을 추천드릴게요.',
});
messages.push(initialMessage);
renderMessages();
scrollToBottom();

messageInput.addEventListener('input', () => {
  autoResizeTextarea();
});

messageInput.addEventListener('paste', async (event) => {
  const clipboardData = event.clipboardData;
  if (!clipboardData) return;
  const file = extractImageFromClipboard(clipboardData);
  if (!file) return;
  await attachImageFile(file, '붙여넣은 이미지');
});

imageInput.addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) {
    clearImageSelection();
    return;
  }
  await attachImageFile(file);
});

removeImageBtn.addEventListener('click', () => {
  clearImageSelection();
});

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text && !selectedImageDataUrl) {
    messageInput.focus();
    return;
  }

  const userMessage = createMessage({
    role: 'user',
    text,
    imageUrl: selectedImageDataUrl,
  });

  appendMessage(userMessage);
  resetComposer();

  const historyPayload = serializeHistory();
  const placeholder = createMessage(
    {
      role: 'assistant',
      text: '생각 중…',
      loading: true,
    },
  );
  appendMessage(placeholder);

  try {
    const response = await sendChatRequest({
      message: userMessage.text,
      imageUrl: userMessage.imageUrl,
      history: historyPayload,
    });
    const assistantMessage = createMessage(
      {
        role: 'assistant',
        text: response.text,
        imageUrl: response.imageUrl || null,
        products: response.products || [],
      },
      placeholder.id,
    );
    replaceMessage(placeholder.id, assistantMessage);
  } catch (error) {
    console.error(error);
    const failMessage = createMessage(
      {
        role: 'assistant',
        text: '잠시 후 다시 시도해주세요. 네트워크 상태를 확인한 뒤 다시 요청 바랍니다.',
      },
      placeholder.id,
    );
    replaceMessage(placeholder.id, failMessage);
  }
});

function renderMessages() {
  messageList.innerHTML = '';
  messages.forEach((message) => {
    messageList.appendChild(createMessageElement(message));
  });
}

function createMessageElement(message) {
  const wrapper = document.createElement('article');
  wrapper.className = `message ${message.role}`;
  if (message.loading) {
    wrapper.classList.add('loading');
  }

  const avatar = document.createElement('div');
  avatar.className = `avatar ${message.role}`;
  avatar.textContent = message.role === 'assistant' ? 'AI' : '나';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (message.loading) {
    const span = document.createElement('span');
    span.textContent = '생각 중…';
    const dots = document.createElement('span');
    dots.className = 'dots';
    dots.innerHTML = '<span></span><span></span><span></span>';
    bubble.append(span, dots);
  } else if (message.text) {
    message.text.split('\n').forEach((paragraph) => {
      const p = document.createElement('p');
      p.textContent = paragraph;
      bubble.appendChild(p);
    });
  }

  if (message.imageUrl) {
    const figure = document.createElement('figure');
    figure.className = 'message-image';

    const img = document.createElement('img');
    img.src = message.imageUrl;
    img.alt = message.role === 'assistant' ? 'AI가 생성한 인테리어 이미지' : '사용자 첨부 이미지';
    figure.appendChild(img);

    const caption = document.createElement('figcaption');
    caption.textContent =
      message.role === 'assistant' ? 'AI가 생성한 인테리어 이미지' : '사용자가 첨부한 참고 이미지';
    figure.appendChild(caption);

    bubble.appendChild(figure);
  }

  if (message.products && message.products.length) {
    const strip = document.createElement('div');
    strip.className = 'product-strip';

    message.products.forEach((product) => {
      console.log('product:', product)
      const productTitle = product.title || product.name || '추천 제품';
      const productImage = product.img || product.thumbnail || '';
      const card = document.createElement('a');
      card.className = 'product-card';
      card.href = product.link;
      card.target = '_blank';
      card.rel = 'noopener noreferrer';
      card.setAttribute('aria-label', `${productTitle} 자세히 보기`);

      if (productImage) {
        console.log('productImage:', productImage)
        const thumb = document.createElement('img');
        thumb.src = productImage;
        thumb.alt = `${productTitle} 썸네일`;
        thumb.loading = 'lazy';
        thumb.decoding = 'async';
        thumb.referrerPolicy = 'no-referrer';
        thumb.addEventListener('error', () => {
          thumb.replaceWith(createProductImageFallback(productTitle));
        });
        card.appendChild(thumb);
      } else {
        card.appendChild(createProductImageFallback(productTitle));
      }

      const body = document.createElement('div');
      body.className = 'card-body';

      const title = document.createElement('h4');
      title.textContent = productTitle;

      const price = document.createElement('div');
      price.className = 'price';
      price.textContent = product.price || '';

      const cta = document.createElement('div');
      cta.className = 'cta';
      cta.textContent = '자세히 보기';

      body.append(title, price, cta);
      card.appendChild(body);
      strip.appendChild(card);
    });

    bubble.appendChild(strip);
  }

  wrapper.append(avatar, bubble);
  return wrapper;
}

function appendMessage(message) {
  messages.push(message);
  renderMessages();
  scrollToBottom();
}

function replaceMessage(id, nextMessage) {
  const index = messages.findIndex((message) => message.id === id);
  if (index === -1) return;
  messages[index] = nextMessage;
  renderMessages();
  scrollToBottom();
}

function resetComposer() {
  chatForm.reset();
  selectedImageDataUrl = null;
  selectedImageName = '';
  updateImagePreview();
  autoResizeTextarea();
}

function updateImagePreview() {
  const hasImage = Boolean(selectedImageDataUrl);
  if (hasImage) {
    previewImage.src = selectedImageDataUrl;
    previewName.textContent = selectedImageName || '첨부된 이미지';
    imagePreviewBar.hidden = false;
    imagePreviewBar.style.display = 'flex';
    imagePreviewBar.setAttribute('aria-hidden', 'false');
  } else {
    imagePreviewBar.hidden = true;
    imagePreviewBar.style.display = 'none';
    imagePreviewBar.setAttribute('aria-hidden', 'true');
    previewImage.removeAttribute('src');
    previewName.textContent = '';
  }
}

function clearImageSelection() {
  selectedImageDataUrl = null;
  selectedImageName = '';
  imageInput.value = '';
  updateImagePreview();
}

function autoResizeTextarea() {
  messageInput.style.height = 'auto';
  const nextHeight = Math.min(messageInput.scrollHeight, 160);
  messageInput.style.height = `${nextHeight}px`;
}

autoResizeTextarea();

function scrollToBottom() {
  requestAnimationFrame(() => {
    chatScroll.scrollTop = chatScroll.scrollHeight;
  });
}

function serializeHistory() {
  return messages
    .filter((message) => !message.loading)
    .map(({ role, text, imageUrl }) => ({
      role,
      text,
      imageUrl: imageUrl || undefined,
    }));
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = (error) => reject(error);
    reader.readAsDataURL(file);
  });
}

async function attachImageFile(file, fallbackName = '') {
  if (!file) {
    clearImageSelection();
    return false;
  }
  if (!file.type.startsWith('image/')) {
    alert('이미지 파일만 업로드할 수 있어요.');
    clearImageSelection();
    return false;
  }
  try {
    selectedImageDataUrl = await readFileAsDataUrl(file);
    selectedImageName = file.name || fallbackName || '첨부된 이미지';
    updateImagePreview();
    return true;
  } catch (error) {
    console.error(error);
    clearImageSelection();
    alert('이미지를 불러오지 못했어요. 다시 시도해주세요.');
    return false;
  }
}

function extractImageFromClipboard(clipboardData) {
  if (!clipboardData) return null;

  const clipboardFiles = clipboardData.files ? Array.from(clipboardData.files) : [];
  const directFile = clipboardFiles.find((file) => file.type && file.type.startsWith('image/'));
  if (directFile) {
    return directFile;
  }

  const items = clipboardData.items ? Array.from(clipboardData.items) : [];
  const imageItem = items.find(
    (item) => item.kind === 'file' && item.type && item.type.startsWith('image/'),
  );
  return imageItem ? imageItem.getAsFile() : null;
}

const BACKEND_BASE_URL = window.__BACKEND_URL__ || 'http://localhost:8001';

async function sendChatRequest(payload) {
  const endpoint = BACKEND_BASE_URL
    ? `${BACKEND_BASE_URL.replace(/\/$/, '')}/chat`
    : '/chat';
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new Error(errorText || 'Failed to fetch from backend');
  }

  const data = await response.json();
  return {
    text: data.text || '',
    imageUrl: data.imageUrl || null,
    products: Array.isArray(data.products) ? data.products : [],
  };
}

function createProductImageFallback(titleText) {
  const fallback = document.createElement('div');
  fallback.className = 'product-thumb-fallback';
  fallback.textContent = '이미지를 불러올 수 없어요';
  if (titleText) {
    fallback.setAttribute('aria-label', `${titleText} 이미지 대체 영역`);
  }
  return fallback;
}

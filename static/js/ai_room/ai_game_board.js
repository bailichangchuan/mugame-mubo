let pieceActionMode = null;
let moveDetailsMap = new Map();

function showPieceActionModal(piece) {
    const modal = document.getElementById('piece-action-modal');
    const title = document.getElementById('piece-action-title');
    const info = document.getElementById('piece-action-info');
    const moveBtn = document.getElementById('btn-action-move');
    const attackBtn = document.getElementById('btn-action-attack');
    
    if (!modal || !title || !info) return;
    
    const pieceTypes = gameState?.piece_types || {};
    const pieceType = pieceTypes[piece.type] || {};
    const pieceName = pieceType.name || piece.type;
    
    title.innerText = `选择「${pieceName}」的动作`;
    
    const stepsLeft = gameState.steps_left || 0;
    info.innerHTML = `剩余步数：<strong>${stepsLeft}</strong> 步`;
    
    moveBtn.style.display = 'inline-block';
    attackBtn.style.display = 'inline-block';
    
    modal.style.display = 'block';
}

function hidePieceActionModal() {
    const modal = document.getElementById('piece-action-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function selectPieceAction(mode) {
    pieceActionMode = mode;
    hidePieceActionModal();
    
    if (mode === 'move') {
        addLog('📍 已选择移动模式，点击绿色区域移动');
    } else if (mode === 'attack') {
        addLog('⚔️ 已选择攻击模式，点击敌方棋子攻击');
    }
    
    renderBoard(globalBoardState);
}

function cancelPieceAction() {
    selectedPiece = null;
    pieceActionMode = null;
    hidePieceActionModal();
    renderBoard(globalBoardState);
    addLog('已取消选择');
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && document.getElementById('piece-action-modal').style.display !== 'none') {
        cancelPieceAction();
    }
});

document.addEventListener('click', function(e) {
    const modal = document.getElementById('piece-action-modal');
    if (!modal) return;
    
    if (modal.style.display !== 'none') {
        const isClickInside = modal.contains(e.target);
        const isModalButton = e.target.closest('#piece-action-modal button');
        
        if (!isClickInside && selectedPiece) {
            const data = viewToData(selectedPiece.r, selectedPiece.c);
            const boardContainer = document.getElementById('game-board');
            const cells = boardContainer.querySelectorAll('.cell');
            
            let clickedOnSelected = false;
            for (const cell of cells) {
                const cellViewR = parseInt(cell.dataset.viewR);
                const cellViewC = parseInt(cell.dataset.viewC);
                const cellData = viewToData(cellViewR, cellViewC);
                
                if (cellData.r === data.r && cellData.c === data.c) {
                    const rect = cell.getBoundingClientRect();
                    if (e.clientX >= rect.left && e.clientX <= rect.right &&
                        e.clientY >= rect.top && e.clientY <= rect.bottom) {
                        clickedOnSelected = true;
                        break;
                    }
                }
            }
            
            if (!clickedOnSelected && !isModalButton) {
                cancelPieceAction();
            }
        }
    }
});

function renderBoard(boardData) {
    globalBoardState = boardData;
    const boardContainer = document.getElementById('game-board');
    boardContainer.innerHTML = '';

    if (!boardData) return;

    const height = boardData.length;
    const width = boardData[0].length;
    const cellSize = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--cell-size')) || 75;
    
    setBoardSize(height, width);
    
    boardContainer.style.gridTemplateColumns = `repeat(${width}, ${cellSize}px)`;
    boardContainer.style.gridTemplateRows = `repeat(${height}, ${cellSize}px)`;
    boardContainer.style.width = `${width * cellSize}px`;
    boardContainer.style.height = `${height * cellSize}px`;

    const terrainData = gameState?.terrain?.type;
    const terrainHeight = gameState?.terrain?.height;
    const terrainTypes = gameState?.terrain_types;
    const pieceTypes = gameState?.piece_types;

    let moveRange = { moves: [], captures: [], details: new Map() };
    
    if (selectedPiece && gameState) {
        const piece = boardData[selectedPiece.r][selectedPiece.c];
        const pos = [selectedPiece.c, selectedPiece.r];
        const stepsLeft = gameState.steps_left || 0;
        moveRange = getMoveRange(piece, pos, stepsLeft, gameState);
        moveDetailsMap = moveRange.details;
    }
    
    for (let viewR = 0; viewR < height; viewR++) {
        for (let viewC = 0; viewC < width; viewC++) {
            const cell = document.createElement('div');
            cell.className = 'cell';
            cell.style.position = 'relative';

            if (viewC === 0 && viewR === 0) {
                cell.classList.add('corner-tl');
            } else if (viewC === width - 1 && viewR === 0) {
                cell.classList.add('corner-tr');
            } else if (viewC === 0 && viewR === height - 1) {
                cell.classList.add('corner-bl');
            } else if (viewC === width - 1 && viewR === height - 1) {
                cell.classList.add('corner-br');
            }

            const data = viewToData(viewR, viewC);
            const moveInfo = moveRange.details.get(`${data.c},${data.r}`);
            
            if (moveInfo) {
                let shouldHighlight = true;
                
                if (pieceActionMode === 'move' && (moveInfo.isRangedAttack || moveInfo.isCapture)) {
                    shouldHighlight = false;
                } else if (pieceActionMode === 'attack' && !moveInfo.isRangedAttack && !moveInfo.isCapture) {
                    shouldHighlight = false;
                }
                
                if (shouldHighlight) {
                    if (moveInfo.isRangedAttack) {
                        cell.classList.add('ranged-attack');
                        addMoveIndicator(cell, '弓', 'ranged');
                    } else if (moveInfo.isCapture) {
                        cell.classList.add('can-capture');
                        addMoveIndicator(cell, moveInfo.cost, 'capture');
                    } else {
                        cell.classList.add('valid-move');
                        addMoveIndicator(cell, moveInfo.cost, 'move');
                    }
                }

                cell.addEventListener('mouseenter', () => {
                    if (!moveInfo.isRangedAttack) {
                        showMovePath(cell, moveInfo);
                    }
                });
                cell.addEventListener('mouseleave', () => {
                    hideMovePath();
                });
            }
            
            if (terrainData) {
                const terrainType = terrainData[data.r][data.c];
                
                if (terrainTypes && terrainTypes[terrainType]) {
                    const terrainColor = terrainTypes[terrainType].color || '#deb887';
                    const heightValue = terrainHeight ? terrainHeight[data.r][data.c] : 0;
                    const absHeight = Math.abs(heightValue);
                    const intensity = Math.min(absHeight / 2, 1);
                    const darkness = intensity * 0.6;
                    
                    const terrainOverlay = document.createElement('div');
                    terrainOverlay.style.position = 'absolute';
                    terrainOverlay.style.top = '0';
                    terrainOverlay.style.left = '0';
                    terrainOverlay.style.right = '0';
                    terrainOverlay.style.bottom = '0';
                    terrainOverlay.style.pointerEvents = 'none';
                    terrainOverlay.style.zIndex = '1';
                    terrainOverlay.style.boxSizing = 'border-box';
                    
                    if (terrainColor.startsWith('#')) {
                        const r = parseInt(terrainColor.slice(1, 3), 16);
                        const g = parseInt(terrainColor.slice(3, 5), 16);
                        const b = parseInt(terrainColor.slice(5, 7), 16);
                        const newR = Math.max(0, Math.round(r * (1 - darkness)));
                        const newG = Math.max(0, Math.round(g * (1 - darkness)));
                        const newB = Math.max(0, Math.round(b * (1 - darkness)));
                        terrainOverlay.style.backgroundColor = `rgb(${newR}, ${newG}, ${newB})`;
                    } else {
                        terrainOverlay.style.backgroundColor = terrainColor;
                    }
                    
                    cell.appendChild(terrainOverlay);
                }
            }

            if (terrainHeight && showTerrainNumbers) {
                const heightValue = terrainHeight[data.r][data.c];
                
                const heightElement = document.createElement('div');
                heightElement.style.position = 'absolute';
                heightElement.style.top = '2px';
                heightElement.style.left = '2px';
                heightElement.style.fontSize = '12px';
                heightElement.style.fontWeight = 'bold';
                heightElement.style.color = '#000000';
                heightElement.style.textShadow = '0 0 2px rgba(255,255,255,0.8)';
                heightElement.style.pointerEvents = 'none';
                heightElement.style.zIndex = '2';
                heightElement.innerText = heightValue;
                
                cell.appendChild(heightElement);
            }

            const piece = boardData[data.r][data.c];

            if (piece) {
                const pDiv = document.createElement('div');
                pDiv.className = `piece side-${piece.side}`;
                
                let pieceText = '散';
                if (pieceTypes && pieceTypes[piece.type]) {
                    const pieceName = pieceTypes[piece.type].name;
                    pieceText = pieceName ? pieceName.charAt(0) : '散';
                }
                pDiv.innerText = pieceText;
                
                if (selectedPiece && selectedPiece.r === data.r && selectedPiece.c === data.c) {
                    pDiv.classList.add('selected');
                }
                
                cell.appendChild(pDiv);
            }
            
            cell.dataset.viewR = viewR;
            cell.dataset.viewC = viewC;
            cell.onclick = () => handleCellClick(viewR, viewC);
            boardContainer.appendChild(cell);
        }
    }
}

function addMoveIndicator(cell, cost, type) {
    const indicator = document.createElement('div');
    indicator.className = `move-indicator move-${type}`;
    indicator.innerText = cost;
    cell.appendChild(indicator);
}

function showMovePath(cell, moveInfo) {
    if (!moveInfo.path || moveInfo.path.length === 0) return;
    
    const boardContainer = document.getElementById('game-board');
    const cells = boardContainer.querySelectorAll('.cell');
    
    moveInfo.path.forEach((pos, index) => {
        const viewCoord = dataToView(pos.row, pos.col);
        const cellIndex = viewCoord.viewR * boardWidth + viewCoord.viewC;
        if (cells[cellIndex]) {
            cells[cellIndex].classList.add('path-highlight');
            cells[cellIndex].style.setProperty('--path-order', index + 1);
        }
    });
    
    cell.classList.add('path-target');
}

function hideMovePath() {
    document.querySelectorAll('.path-highlight').forEach(el => {
        el.classList.remove('path-highlight');
        el.style.removeProperty('--path-order');
    });
    document.querySelectorAll('.path-target').forEach(el => {
        el.classList.remove('path-target');
    });
}

let clickTimer = null;

function handleCellClick(viewR, viewC) {
    if (isGameLocked) {
        return;
    }
    const isMyTurn = (gameState.turn === p1Id) === (myUserId === p1Id);
    if (!isMyTurn || isAIThinking) {
        if (isAIThinking) {
            addLog('⚠️ AI正在思考中，请等待...');
        }
        return;
    }

    const data = viewToData(viewR, viewC);
    const piece = globalBoardState[data.r][data.c];

    if (gameState.pending_combat && gameState.pending_combat.active) {
        addLog("⚠️ 正在决斗阶段，无法移动");
        return;
    }

    if (!selectedPiece) {
        if (piece && piece.side === mySide) {
            selectedPiece = { r: data.r, c: data.c };
            soundFX.playClick();
            showPieceActionModal(piece);
        }
    } else {
        if (selectedPiece.r === data.r && selectedPiece.c === data.c) {
            selectedPiece = null;
            pieceActionMode = null;
            renderBoard(globalBoardState);
            return;
        }
        
        if (piece && piece.side === mySide) {
            selectedPiece = { r: data.r, c: data.c };
            pieceActionMode = null;
            soundFX.playClick();
            showPieceActionModal(piece);
            return;
        }
        
        const attacker = gameState.board[selectedPiece.r][selectedPiece.c];
        const pos = [selectedPiece.c, selectedPiece.r];
        const moves = getValidMoves(attacker, pos, gameState.steps_left || 0, gameState);
        const isValidMove = moves.moves.some(m => m.row === data.r && m.col === data.c);
        const isValidCapture = moves.captures.some(c => c.row === data.r && c.col === data.c);
        
        if (isValidMove && (!pieceActionMode || pieceActionMode === 'move')) {
            if (clickTimer) {
                clearTimeout(clickTimer);
                clickTimer = null;
            }
            handlePlayerMove(selectedPiece.r, selectedPiece.c, data.r, data.c);
            selectedPiece = null;
            pieceActionMode = null;
            return;
        }
        
        if (isValidCapture && (!pieceActionMode || pieceActionMode === 'attack')) {
            if (clickTimer) {
                clearTimeout(clickTimer);
                clickTimer = null;
            }
            handlePlayerMove(selectedPiece.r, selectedPiece.c, data.r, data.c);
            selectedPiece = null;
            pieceActionMode = null;
            return;
        }
        
        selectedPiece = null;
        pieceActionMode = null;
        renderBoard(globalBoardState);
    }
}

function handlePlayerMove(fromR, fromC, toR, toC) {
    const fromPos = [fromC, fromR];
    const toPos = [toC, toR];

    const attacker = gameState.board[fromR][fromC];
    const target = gameState.board[toR][toC];

    if (!attacker) {
        addLog('❌ 没有选择棋子');
        return;
    }

    const moveInfo = getMoveInfo(toR, toC);
    if (moveInfo && moveInfo.isRangedAttack && target && target.side !== mySide) {
        initiateCombat(fromPos, toPos);
        return;
    }

    const pathResult = calculatePathCost(fromPos, toPos, gameState, attacker);
    if (pathResult.cost > (gameState.steps_left || 0)) {
        if (target && target.side !== mySide && isRangedPiece(attacker)) {
            addLog(`❌ 目标超出攻击范围，需要移动后攻击`);
        } else {
            addLog(`❌ 步数不足，无法到达该位置`);
        }
        return;
    }

    if (target && target.side !== mySide) {
        initiateCombat(fromPos, toPos);
    } else if (!target) {
        executeMove(fromPos, toPos, pathResult.cost);
    } else {
        addLog('❌ 不能移动到己方棋子位置');
    }
}

function executeMove(fromPos, toPos, moveCost) {
    const [fromC, fromR] = fromPos;
    const [toC, toR] = toPos;
    
    const attacker = gameState.board[fromR][fromC];
    
    if (gameState.steps_left < moveCost) {
        addLog(`❌ 步数不足，移动需要 ${moveCost} 步`);
        return;
    }

    gameState.board[toR][toC] = attacker;
    gameState.board[fromR][fromC] = null;
    gameState.steps_left -= moveCost;

    addLog(`✅ 棋子移动到 (${toC}, ${toR})，消耗 ${moveCost} 步`);
    soundFX.playPieceMove();

    renderBoard(gameState.board);
    updateInfo();
    saveGameStateToCookie();
}

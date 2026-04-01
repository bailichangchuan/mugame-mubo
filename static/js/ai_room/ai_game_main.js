// ========== LocalStorage 存储系统 ==========

const STORAGE_KEY = 'liubo_game_state';
const STORAGE_EXPIRY_DAYS = 7;

function saveGameStateToCookie() {
    if (!gameState || gameState.winner) return;

    const stateToSave = {
        board: gameState.board,
        turn: gameState.turn,
        steps_left: gameState.steps_left,
        has_rolled: gameState.has_rolled,
        rolled_by_player: gameState.rolled_by_player,
        turn_number: gameState.turn_number,
        pending_combat: gameState.pending_combat,
        has_used_cannon: gameState.has_used_cannon,
        terrain: gameState.terrain,
        terrain_types: gameState.terrain_types,
        piece_types: gameState.piece_types,
        cards: gameState.cards,
        winner: gameState.winner,
        timestamp: Date.now()
    };

    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(stateToSave));
        console.log('[Storage] 游戏状态已保存到 localStorage');
    } catch (e) {
        console.error('[Storage] 保存失败:', e);
    }
}

function loadGameStateFromCookie() {
    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (!saved) {
            console.log('[Storage] 没有找到保存的状态');
            return null;
        }

        const state = JSON.parse(saved);
        const age = Date.now() - (state.timestamp || 0);
        const maxAge = STORAGE_EXPIRY_DAYS * 24 * 60 * 60 * 1000;

        if (age > maxAge) {
            console.log('[Storage] 保存的状态已过期');
            localStorage.removeItem(STORAGE_KEY);
            return null;
        }

        if (state.winner) {
            console.log('[Storage] 游戏已结束，忽略保存的状态');
            localStorage.removeItem(STORAGE_KEY);
            return null;
        }

        console.log('[Storage] 从 localStorage 恢复游戏状态');
        return state;
    } catch (e) {
        console.error('[Storage] 恢复失败:', e);
        localStorage.removeItem(STORAGE_KEY);
        return null;
    }
}

function clearGameStateCookie() {
    localStorage.removeItem(STORAGE_KEY);
    console.log('[Storage] 游戏状态已清除');
}

// ========== 战斗系统 ==========

let strategyCardModalCallback = null;
let aiStrategyCards = null;

function initializeAIStrategyCards() {
    if (typeof STRATEGY_CARDS !== 'undefined' && typeof strategyCardCounts !== 'undefined') {
        aiStrategyCards = JSON.parse(JSON.stringify(strategyCardCounts));
    }
}

function getAIStrategyCards() {
    return aiStrategyCards || {};
}

function getAvailableAIStrategyCards() {
    if (!aiStrategyCards) return [];
    const cards = [];
    for (const cardId in aiStrategyCards) {
        if (aiStrategyCards[cardId] > 0) {
            cards.push({
                id: cardId,
                name: typeof STRATEGY_CARDS !== 'undefined' ? STRATEGY_CARDS[cardId].name : cardId,
                minValue: typeof STRATEGY_CARDS !== 'undefined' ? STRATEGY_CARDS[cardId].minValue : 0
            });
        }
    }
    return cards;
}

function calculateCombatImportance(attacker, defender, distance) {
    const attackerValue = attacker.val || 0;
    const defenderValue = defender.val || 0;
    const totalValue = attackerValue + defenderValue;
    const isRanged = distance > 1;
    let importance = totalValue;

    if (defenderValue > attackerValue * 1.5) {
        importance *= 1.5;
    }

    if (attackerValue >= 16) {
        importance *= 1.3;
    }

    if (isRanged) {
        importance *= 0.8;
    }

    return importance;
}

function shouldAIUseStrategyCard(attacker, defender, distance, combatImportance) {
    if (!aiStrategyCards) return null;

    const availableCards = getAvailableAIStrategyCards();
    if (availableCards.length === 0) return null;

    const sortedCards = availableCards.sort((a, b) => b.minValue - a.minValue);

    const threshold = 40;
    if (combatImportance < threshold) return null;

    for (const card of sortedCards) {
        if (combatImportance >= card.minValue) {
            return card;
        }
    }

    return null;
}

function useAIStrategyCard(cardId) {
    if (!aiStrategyCards || !aiStrategyCards[cardId]) return false;
    aiStrategyCards[cardId]--;
    return true;
}

function showStrategyCardPrompt(onSelect) {
    const modal = document.getElementById('strategy-card-modal');
    const title = document.getElementById('strategy-card-title');
    const desc = document.getElementById('strategy-card-desc');
    const buttons = document.getElementById('strategy-card-buttons');

    title.textContent = '🎴 战斗锦囊';
    desc.textContent = '是否使用战斗锦囊来增强你的战力？';

    strategyCardModalCallback = onSelect;

    const availableCards = [];
    if (typeof strategyCardCounts !== 'undefined') {
        for (const cardId in strategyCardCounts) {
            if (strategyCardCounts[cardId] > 0) {
                availableCards.push({
                    id: cardId,
                    name: typeof STRATEGY_CARDS !== 'undefined' ? STRATEGY_CARDS[cardId].name : cardId,
                    minValue: typeof STRATEGY_CARDS !== 'undefined' ? STRATEGY_CARDS[cardId].minValue : 0
                });
            }
        }
    }

    let buttonsHtml = '';

    if (availableCards.length > 0) {
        availableCards.forEach(card => {
            buttonsHtml += `<button class="strategy-btn strategy-btn-use" onclick="useStrategyCardFromModal('${card.id}', '${card.name}', ${card.minValue})">${card.name} (战力>${card.minValue})</button>`;
        });
    }

    buttonsHtml += `<button class="strategy-btn strategy-btn-skip" onclick="skipStrategyCard()">不使用</button>`;

    buttons.innerHTML = buttonsHtml;
    modal.style.display = 'block';
}

function useStrategyCardFromModal(cardId, cardName, minValue) {
    const modal = document.getElementById('strategy-card-modal');
    modal.style.display = 'none';

    if (typeof strategyCardCounts !== 'undefined' && strategyCardCounts[cardId] > 0) {
        strategyCardCounts[cardId]--;
        const countEl = document.getElementById('count-' + cardId);
        if (countEl) countEl.innerText = strategyCardCounts[cardId];

        const cardEl = document.getElementById('card-' + cardId);
        if (cardEl) {
            cardEl.classList.remove('selected');
            cardEl.classList.add('used');
            setTimeout(() => cardEl.classList.remove('used'), 500);
        }

        addLog(`🎴 使用锦囊: ${cardName}`);
    }

    if (strategyCardModalCallback) {
        const callback = strategyCardModalCallback;
        strategyCardModalCallback = null;
        callback(minValue);
    }
}

function skipStrategyCard() {
    const modal = document.getElementById('strategy-card-modal');
    modal.style.display = 'none';

    if (strategyCardModalCallback) {
        const callback = strategyCardModalCallback;
        strategyCardModalCallback = null;
        callback(0);
    }
}

function initiateCombat(fromPos, toPos) {
    const [fromC, fromR] = fromPos;
    const [toC, toR] = toPos;
    const attacker = gameState.board[fromR][fromC];
    const target = gameState.board[toR][toC];

    const dist = Math.abs(fromR - toR) + Math.abs(fromC - toC);

    gameState.pending_combat = {
        active: true,
        distance: dist,
        attacker: {
            pos: [fromC, fromR],
            side: attacker.side,
            sticks: null,
            val: null,
            has_rolled: false,
            cardBonus: 0
        },
        defender: {
            pos: [toC, toR],
            side: target.side,
            sticks: null,
            val: null,
            has_rolled: false
        }
    };

    addLog('⚔️ 发起战斗！');
    renderBoard(gameState.board);
    updateInfo();

    if (attacker.side === 'R' && typeof strategyCardCounts !== 'undefined') {
        let hasAvailableCard = false;
        for (const cardId in strategyCardCounts) {
            if (strategyCardCounts[cardId] > 0) {
                hasAvailableCard = true;
                break;
            }
        }

        if (hasAvailableCard) {
            showStrategyCardPrompt((cardBonus) => {
                gameState.pending_combat.attacker.cardBonus = cardBonus;
                playerCombatRoll();
            });
        } else {
            playerCombatRoll();
        }
    } else {
        playerCombatRoll();
    }
}

function playerCombatRoll() {
    const combat = gameState.pending_combat;
    if (!combat || !combat.active) return;

    soundFX.playDiceRoll();

    const rollAnim = document.getElementById('roll-animation');
    if (rollAnim) {
        rollAnim.style.display = 'block';
    }

    const sticks = Array.from({length: 6}, () => Math.random() < 0.5 ? 1 : 0);

    animateDiceRoll(sticks, () => {
        setTimeout(() => {
            const binaryStr = sticks.join('');
            const val = parseInt(binaryStr, 2);

            combat.attacker.sticks = sticks;
            combat.attacker.binary_str = binaryStr;
            combat.attacker.val = val;
            combat.attacker.has_rolled = true;

            if (rollAnim) {
                rollAnim.style.display = 'none';
            }

            soundFX.playClick();
            addLog(`🎲 玩家掷出 ${sticks.join('')} = ${val}`);

            if (!combat.defender.has_rolled) {
                setTimeout(() => aiCombatRoll(), 500);
            } else {
                resolveCombat();
            }
        }, 300);
    }, 'player', '战斗攻击');
}

function aiCombatRoll() {
    const combat = gameState.pending_combat;
    if (!combat || !combat.active) return;

    soundFX.playDiceRoll();

    const rollAnim = document.getElementById('roll-animation');
    if (rollAnim) {
        rollAnim.style.display = 'block';
    }

    const sticks = Array.from({length: 6}, () => Math.random() < 0.5 ? 1 : 0);

    animateDiceRoll(sticks, () => {
        setTimeout(() => {
            const binaryStr = sticks.join('');
            const val = parseInt(binaryStr, 2);

            combat.defender.sticks = sticks;
            combat.defender.binary_str = binaryStr;
            combat.defender.val = val;
            combat.defender.has_rolled = true;

            if (rollAnim) {
                rollAnim.style.display = 'none';
            }

            addLog(`🎲 AI掷出 ${sticks.join('')} = ${val}`);

            resolveCombat();
        }, 300);
    }, 'AI', '战斗防御');
}

function aiAttackerCombatRoll() {
    const combat = gameState.pending_combat;
    if (!combat || !combat.active) return;

    soundFX.playDiceRoll();

    const rollAnim = document.getElementById('roll-animation');
    if (rollAnim) {
        rollAnim.style.display = 'block';
    }

    const sticks = Array.from({length: 6}, () => Math.random() < 0.5 ? 1 : 0);

    animateDiceRoll(sticks, () => {
        setTimeout(() => {
            const binaryStr = sticks.join('');
            const val = parseInt(binaryStr, 2);

            combat.attacker.sticks = sticks;
            combat.attacker.binary_str = binaryStr;
            combat.attacker.val = val;
            combat.attacker.has_rolled = true;

            if (rollAnim) {
                rollAnim.style.display = 'none';
            }

            addLog(`🎲 AI掷出 ${sticks.join('')} = ${val}`);

            if (!combat.defender.has_rolled) {
                setTimeout(() => playerDefenderCombatRoll(), 500);
            } else {
                resolveCombat();
            }
        }, 300);
    }, 'AI', '战斗攻击');
}

function playerDefenderCombatRoll() {
    const combat = gameState.pending_combat;
    if (!combat || !combat.active) return;

    soundFX.playDiceRoll();

    const rollAnim = document.getElementById('roll-animation');
    if (rollAnim) {
        rollAnim.style.display = 'block';
    }

    const sticks = Array.from({length: 6}, () => Math.random() < 0.5 ? 1 : 0);

    animateDiceRoll(sticks, () => {
        setTimeout(() => {
            const binaryStr = sticks.join('');
            const val = parseInt(binaryStr, 2);

            combat.defender.sticks = sticks;
            combat.defender.binary_str = binaryStr;
            combat.defender.val = val;
            combat.defender.has_rolled = true;

            if (rollAnim) {
                rollAnim.style.display = 'none';
            }

            soundFX.playClick();
            addLog(`🎲 玩家掷出 ${sticks.join('')} = ${val}`);

            resolveCombat();
        }, 300);
    }, 'player', '战斗防御');
}

function resolveCombat() {
    const combat = gameState.pending_combat;
    if (!combat || !combat.active) return;

    soundFX.playCombatStart();

    const [atkC, atkR] = combat.attacker.pos;
    const [defC, defR] = combat.defender.pos;
    const attacker = gameState.board[atkR][atkC];
    const defender = gameState.board[defR][defC];

    if (!attacker || !defender) {
        gameState.pending_combat = null;
        return;
    }

    let heightDiff = 0;
    if (gameState.terrain?.height) {
        const currentHeight = gameState.terrain.height[atkR]?.[atkC] || 0;
        const targetHeight = gameState.terrain.height[defR]?.[defC] || 0;
        heightDiff = currentHeight - targetHeight;
    }

    const dist = combat.distance;
    const k = 0.1 + Math.floor(((gameState.turn_number || 1) - 1) / 10) * 0.1;

    const combatBonus = combat.attacker.cardBonus || 0;

    let atkPower = CombatCalculator.calculatePower(
        attacker, 
        combat.attacker.val, 
        dist, 
        'attacker', 
        defender,
        [atkC, atkR],
        gameState.terrain_types,
        gameState.terrain,
        heightDiff,
        gameState.piece_types,
        gameState.board,
        combat.attacker.side,
        k
    );
    
    if (combatBonus > 0) {
        atkPower = Math.max(atkPower, combatBonus);
        addLog(`⚔️ 锦囊加成: 战力提升至 ${atkPower.toFixed(1)}`);
    }

    let isRangedAttack = false;
    if (gameState.piece_types?.[attacker.type]) {
        isRangedAttack = gameState.piece_types[attacker.type].attack_type === 'ranged';
    } else {
        isRangedAttack = ['T', 'P'].includes(attacker.type);
    }

    let isMeleeDefender = false;
    if (defender) {
        if (gameState.piece_types?.[defender.type]) {
            isMeleeDefender = gameState.piece_types[defender.type].attack_type === 'melee';
        } else {
            isMeleeDefender = ['S', 'X', 'G'].includes(defender.type);
        }
    }
    const isNonAdjacent = dist > 1;

    const isCannonAttackTerrain = attacker.type === 'P' && combat.defender.is_terrain;

    let defPower = 0;
    if (!isCannonAttackTerrain && defender) {
        defPower = CombatCalculator.calculatePower(
            defender, 
            combat.defender.val, 
            dist, 
            'defender', 
            attacker,
            [defC, defR],
            gameState.terrain_types,
            gameState.terrain,
            -heightDiff,
            gameState.piece_types,
            gameState.board,
            combat.defender.side,
            k
        );
    }

    const combatLog = {
        attacker: {
            val: combat.attacker.val,
            final_power: atkPower,
            side: combat.attacker.side,
            binary_str: combat.attacker.binary_str
        },
        defender: {
            val: combat.defender.val,
            final_power: defPower,
            side: combat.defender.side,
            binary_str: combat.defender.binary_str
        },
        distance: dist,
        winner: null,
        msg: ''
    };

    let remoteAttackHandled = false;

    if (isCannonAttackTerrain) {
        if (atkPower > 30) {
            combatLog.winner = 'attacker';
            combatLog.msg = `炮攻击成功！战力 ${atkPower} > 30`;

            if (gameState.terrain?.height) {
                const currentHeight = gameState.terrain.height[defR][defC];
                const newHeight = Math.max(-1, currentHeight - 1);
                gameState.terrain.height[defR][defC] = newHeight;
                combatLog.msg += `，地形高度降低至 ${newHeight}`;
            }

            if (defender && defender.type === 'X') {
                gameState.winner = attacker.side;
                combatLog.msg = `🎯 枭被击杀！${attacker.side === 'R' ? '红方' : '黑方'}获胜！`;
            } else if (defender) {
                gameState.board[defR][defC] = null;
                generateAndGiveRecruitCard(gameState, combat.defender.side, combatLog);
            }
        } else {
            combatLog.winner = 'draw';
            combatLog.msg = `炮攻击失败 (${atkPower} <= 30)`;
        }
    } else if (attacker.type === 'T' && dist === 3) {
        remoteAttackHandled = true;
        if (atkPower > defPower && atkPower > 20) {
            combatLog.winner = 'attacker';

            if (defender.type === 'X') {
                gameState.winner = attacker.side;
                combatLog.msg = `🎯 枭被远程击杀！${attacker.side === 'R' ? '红方' : '黑方'}获胜！`;
                addLog(`🏆 ${attacker.side === 'R' ? '红方' : '黑方'}获胜！`);
            } else {
                combatLog.msg = `远程狙击成功！战力 ${atkPower} > ${defPower} 且 > 20`;
                gameState.board[defR][defC] = null;
                generateAndGiveRecruitCard(gameState, combat.defender.side, combatLog);
            }
        } else {
            combatLog.winner = 'draw';
            combatLog.msg = `远程被格挡 (${atkPower} < 20)`;
        }
    } else if (isRangedAttack && isMeleeDefender && isNonAdjacent) {
        remoteAttackHandled = true;
        if (atkPower > defPower && atkPower > 20) {
            combatLog.winner = 'attacker';

            if (defender.type === 'X') {
                gameState.winner = attacker.side;
                combatLog.msg = `🎯 枭被远程击杀！${attacker.side === 'R' ? '红方' : '黑方'}获胜！`;
                addLog(`🏆 ${attacker.side === 'R' ? '红方' : '黑方'}获胜！`);
            } else {
                combatLog.msg = `远程攻击胜利 (${atkPower} > ${defPower} 且 > 20)`;
                gameState.board[defR][defC] = null;
                generateAndGiveRecruitCard(gameState, combat.defender.side, combatLog);
            }
        } else {
            combatLog.winner = 'draw';
            combatLog.msg = `进攻失败 (${atkPower} vs ${defPower})，未满足远程攻击条件`;
        }
    } else {
        if (!remoteAttackHandled) {
            if (atkPower > defPower) {
                combatLog.winner = 'attacker';

                if (defender.type === 'X') {
                    gameState.winner = attacker.side;
                    combatLog.msg = `🎯 枭被击杀！${attacker.side === 'R' ? '红方' : '黑方'}获胜！`;
                    addLog(`🏆 ${attacker.side === 'R' ? '红方' : '黑方'}获胜！`);
                } else {
                    combatLog.msg = `进攻胜利 (${atkPower} vs ${defPower})`;
                    gameState.board[defR][defC] = attacker;
                    gameState.board[atkR][atkC] = null;
                    generateAndGiveRecruitCard(gameState, combat.defender.side, combatLog);
                }
            } else {
                combatLog.winner = 'defender';

                if (attacker.type === 'X') {
                    gameState.winner = defender.side;
                    combatLog.msg = `🎯 枭被击杀！${defender.side === 'R' ? '红方' : '黑方'}获胜！`;
                    addLog(`🏆 ${defender.side === 'R' ? '红方' : '黑方'}获胜！`);
                    gameState.board[atkR][atkC] = null;
                    generateAndGiveRecruitCard(gameState, combat.attacker.side, combatLog);
                } else {
                    combatLog.msg = `防守反杀 (${defPower} >= ${atkPower})`;
                    gameState.board[atkR][atkC] = null;
                    generateAndGiveRecruitCard(gameState, combat.attacker.side, combatLog);
                }
            }
        }
    }

    gameState.steps_left -= 1;
    gameState.pending_combat = null;

    renderBoard(gameState.board);
    updateInfo();
    addLog(`⚔️ ${combatLog.msg}`);
    saveGameStateToCookie();

    let combatCallbackExecuted = false;

    const continueAfterCombat = () => {
        if (combatCallbackExecuted) return;
        combatCallbackExecuted = true;

        if (gameState.winner) {
            soundFX.playVictory();
            clearGameStateCookie();
            addLog('🎉 游戏结束！' + (gameState.winner === 'B' ? 'AI获胜' : '玩家获胜'));

            setTimeout(() => {
                if (confirm('是否再来一局？')) {
                    location.reload();
                }
            }, 2000);
        } else if (combatLog.winner === 'attacker') {
            soundFX.playVictory();
            if (gameState.steps_left > 0) {
                if (combat.attacker.side === 'B') {
                    executeAIMove();
                } else {
                    updateInfo();
                }
            } else {
                if (combat.attacker.side === 'B') {
                    endAITurn();
                } else {
                    endTurn();
                }
            }
        } else if (combatLog.winner === 'defender') {
            soundFX.playDefeat();
            if (gameState.steps_left > 0) {
                if (combat.attacker.side === 'B') {
                    executeAIMove();
                } else {
                    updateInfo();
                }
            } else {
                if (combat.attacker.side === 'B') {
                    endAITurn();
                } else {
                    endTurn();
                }
            }
        } else {
            if (gameState.steps_left > 0) {
                if (combat.attacker.side === 'B') {
                    executeAIMove();
                } else {
                    updateInfo();
                }
            } else {
                if (combat.attacker.side === 'B') {
                    endAITurn();
                } else {
                    endTurn();
                }
            }
        }
    };

    showCombatModal(combatLog, continueAfterCombat);

    setTimeout(() => {
        if (!combatCallbackExecuted) {
            const modal = document.getElementById('combat-modal');
            if (modal && modal.style.display !== 'none') {
                dismissCombatModal();
            }
        }
    }, 5000);
}

function generateAndGiveRecruitCard(state, loserSide, combatLog) {
    const pieceTypes = state.piece_types || {};
    const pieceTypeList = Object.keys(pieceTypes).filter(type => type !== 'X');
    
    if (pieceTypeList.length === 0) return;
    
    const pieceType = pieceTypeList[Math.floor(Math.random() * pieceTypeList.length)];
    const recruitCard = `card_recruit_${pieceType}`;
    const pieceName = pieceTypes[pieceType]?.name || pieceType;
    const recruitCardName = `招募${pieceName}`;

    const loserUserId = loserSide === 'R' ? p1Id : -1;

    if (!state.cards) state.cards = {};
    if (!state.cards[loserUserId]) state.cards[loserUserId] = {};

    state.cards[loserUserId][recruitCard] = (state.cards[loserUserId][recruitCard] || 0) + 1;

    const loserName = loserSide === 'R' ? '你已' : 'AI已';
    const motivation = loserSide === 'R' ? '我们将血战到底！' : 'AI正在重整旗鼓...';
    combatLog.msg += `，${loserName}招募新士兵 ${pieceName}！${motivation}`;
    combatLog.recruit_card_gained = recruitCard;
    combatLog.recruit_card_name = recruitCardName;
    combatLog.recruit_card_owner = loserSide;
    
    setTimeout(() => {
        autoDeployRecruitedPiece(state, loserSide, pieceType, recruitCardName);
    }, 100);
}

function autoDeployRecruitedPiece(state, side, pieceType, cardName) {
    if (!state.board) return;
    
    const height = state.board.length;
    const width = state.board[0].length;
    
    const emptyPositions = [];
    for (let r = 0; r < height; r++) {
        for (let c = 0; c < width; c++) {
            if (!state.board[r][c]) {
                emptyPositions.push({ r, c });
            }
        }
    }
    
    if (emptyPositions.length === 0) {
        addLog(`⚠️ ${side === 'R' ? '红方' : '黑方'}无法部署 ${cardName}，棋盘已满`);
        return;
    }
    
    const pos = emptyPositions[Math.floor(Math.random() * emptyPositions.length)];
    const pieceInfo = state.piece_types?.[pieceType] || { name: pieceType };
    state.board[pos.r][pos.c] = {
        type: pieceType,
        side: side,
        power: pieceInfo.base_power || 1.0,
        defense: pieceInfo.defense_power || 1.0
    };
    
    addLog(`🎴 ${side === 'R' ? '红方' : '黑方'}自动部署: ${cardName} 到 (${pos.c}, ${pos.r})`);
    renderBoard(state.board);
    saveGameStateToCookie();
}

// ========== 回合系统 ==========

function createDiceElement(index, finalValue, roller) {
    const dice = document.createElement('img');
    dice.className = 'binary-dice';
    
    let imgSrc;
    if (roller === 'player') {
        imgSrc = finalValue === 1 ? RED_PICTURE : BLACK_PICTURE;
    } else {
        imgSrc = finalValue === 1 ? BLACK_PICTURE : RED_PICTURE;
    }
    dice.src = imgSrc;
    
    dice.style.cssText = `
         width: 5%;
         opacity: 0;
         transform: scale(0.5);
         transition: all 0.3s ease;
     `;
    dice.dataset.index = index;
    dice.alt = finalValue === 1 ? '一' : '零';
    return dice;
}

function animateDiceRoll(finalSticks, onComplete, roller, reason) {
    const diceAnimation = document.getElementById('dice-animation');
    const rollTitle = document.getElementById('roll-title');
    if (!diceAnimation) {
        if (onComplete) onComplete();
        return;
    }

    if (rollTitle) {
        const rollerText = roller === 'AI' ? '🤖 AI' : (roller === 'player' ? '🔴 红方' : '🎲');
        const reasonText = reason ? `（${reason}）` : '';
        rollTitle.innerHTML = `${rollerText} 掷采中 ${reasonText}`;
    }

    diceAnimation.innerHTML = '';

    for (let i = 0; i < 6; i++) {
        setTimeout(() => {
            const dice = createDiceElement(i, finalSticks[i], roller);
            diceAnimation.appendChild(dice);

            setTimeout(() => {
                dice.style.opacity = '1';
                dice.style.transform = 'scale(1)';

                if (i === 5 && onComplete) {
                    setTimeout(() => {
                        onComplete();
                    }, 1500);
                }
            }, 50);
        }, i * 300);
    }
}

function autoRollForPlayer() {
    console.log('[DEBUG] autoRollForPlayer 被调用');
    console.log('[DEBUG] isAIThinking:', isAIThinking, 'has_rolled:', gameState.has_rolled, 'rolled_by_player:', gameState.rolled_by_player);
    if (isAIThinking || gameState.has_rolled || gameState.rolled_by_player) {
        console.log('[DEBUG] autoRollForPlayer 被阻止');
        return;
    }

    soundFX.playDiceRoll();

    const rollAnim = document.getElementById('roll-animation');
    if (rollAnim) {
        rollAnim.style.display = 'block';
    }

    const finalSticks = Array.from({length: 6}, () => Math.random() < 0.5 ? 1 : 0);
    const finalSteps = finalSticks.reduce((a, b) => a + b, 0);

    animateDiceRoll(finalSticks, () => {
        setTimeout(() => {
            gameState.steps_left = finalSteps;
            gameState.has_rolled = true;
            gameState.rolled_by_player = true;

            const rollBtn = document.getElementById('btn-roll');
            if (rollBtn) {
                rollBtn.disabled = true;
                rollBtn.innerText = `已掷: ${finalSteps}步`;
            }
            soundFX.playClick();

            if (rollAnim) {
                rollAnim.style.display = 'none';
            }

            addLog(`🎲 掷出 ${finalSticks.join('')}，得 ${finalSteps} 步`);
            renderBoard(gameState.board);
            updateInfo();

            if (finalSteps === 0) {
                showZeroRollModal();
            } else {
                saveGameStateToCookie();
            }
        }, 500);
    }, 'player', '获取步数');
}

function showZeroRollModal() {
    const modal = document.getElementById('zero-roll-modal');
    if (modal) {
        modal.style.display = 'block';
    }
}

function closeZeroRollModal() {
    const modal = document.getElementById('zero-roll-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    addLog('🔄 回合结束');
    soundFX.playTurnEnd();
    endTurn();
}

function endTurnManual() {
    if (!gameState) {
        addLog('⚠️ 游戏未初始化');
        return;
    }
    if (isAIThinking) {
        addLog('⚠️ AI正在思考中，请等待...');
        return;
    }
    if (gameState.steps_left > 0) {
        addLog('⚠️ 还有剩余步数，无法提前结束回合');
        return;
    }
    endTurn();
}

function skipTurn() {
    console.log('[DEBUG] skipTurn 被调用');
    console.log('[DEBUG] gameState:', gameState);
    console.log('[DEBUG] p1Id:', p1Id);
    console.log('[DEBUG] isAIThinking:', isAIThinking);
    
    if (!gameState) {
        addLog('⚠️ 游戏未初始化');
        return;
    }
    if (isAIThinking) {
        addLog('⚠️ AI正在思考中，请等待...');
        return;
    }
    if (gameState.turn !== p1Id) {
        addLog('⚠️ 当前不是你的回合');
        return;
    }
    if (gameState.has_rolled === false && gameState.rolled_by_player === false) {
        addLog('⚠️ 请先掷采');
        return;
    }
    if (gameState.steps_left <= 0) {
        addLog('⏭️ 跳过回合');
        soundFX.playClick();
        saveGameStateToCookie();
        endTurn();
        return;
    }
    addLog('⏭️ 跳过剩余步数');
    soundFX.playClick();
    endTurn();
}

function endTurn() {
    gameState.turn = gameState.turn === p1Id ? -1 : p1Id;
    gameState.has_rolled = false;
    gameState.steps_left = 0;
    gameState.rolled_by_player = false;
    
    if (gameState.has_used_cannon) {
        gameState.has_used_cannon = {};
    }

    gameState.turn_number = (gameState.turn_number || 1) + 1;

    addLog('🔄 回合结束');
    soundFX.playTurnEnd();
    renderBoard(gameState.board);
    updateInfo();
    resetStrategyCardsForNewTurn();

    if (gameState.turn !== p1Id) {
        waitForAnnouncement(() => executeAITurn());
    }
}

function restoreFromSave() {
    const restoreModal = document.getElementById('restore-modal');
    if (restoreModal) {
        restoreModal.style.display = 'none';
    }
    
    const savedState = window._pendingRestoreState;
    if (!savedState) {
        return;
    }
    
    console.log('[DEBUG] 从 localStorage 恢复游戏');
    console.log('[DEBUG] savedState.turn:', savedState.turn, 'p1Id:', p1Id);
    console.log('[DEBUG] savedState.has_rolled:', savedState.has_rolled);
    console.log('[DEBUG] savedState.steps_left:', savedState.steps_left);
    
    initializeGameState(savedState);
    initializeAIStrategyCards();

    if (gameState.cards && typeof strategyCardCounts !== 'undefined') {
        for (const cardId in gameState.cards) {
            if (strategyCardCounts[cardId] !== undefined) {
                strategyCardCounts[cardId] = gameState.cards[cardId] || 0;
            }
        }
    }

    renderBoard(gameState.board);
    updateInfo();
    updateButtonState();

    console.log('[DEBUG] 恢复后 gameState.turn:', gameState.turn, 'p1Id:', p1Id);
    console.log('[DEBUG] 恢复后 gameState.has_rolled:', gameState.has_rolled);
    console.log('[DEBUG] 恢复后 gameState.steps_left:', gameState.steps_left);
    
    addLog('🔄 从存档恢复游戏！');

    const welcomeScreen = document.getElementById('welcome-screen');
    if (welcomeScreen) {
        welcomeScreen.classList.remove('show');
    }

    isInitializing = false;

    showTurnAnnouncement('R', () => {
        isGameLocked = false;
        if (gameState.turn !== p1Id) {
            waitForAnnouncement(() => executeAITurn());
        } else {
            setTimeout(() => startPlayerTurn(), 500);
        }
    });
}

function giveUpSave() {
    const restoreModal = document.getElementById('restore-modal');
    if (restoreModal) {
        restoreModal.style.display = 'none';
    }
    
    clearGameStateCookie();
    
    location.reload();
}

// ========== AI回合 ==========

function executeAITurn() {
    if (!aiPlayer) {
        addLog('❌ AI未初始化');
        return;
    }

    addLog('🤖 AI回合开始...');
    soundFX.playAIThinking();

    setTimeout(() => {
        isAIThinking = true;
        const aiStatusInline = document.getElementById('ai-status-inline');
        if (aiStatusInline) {
            aiStatusInline.innerText = 'AI思考中...';
            aiStatusInline.classList.add('ai-thinking');
        }

        setTimeout(() => {
            soundFX.playDiceRoll();
            const sticks = Array.from({length: 6}, () => Math.random() < 0.5 ? 1 : 0);
            const moveSteps = sticks.reduce((a, b) => a + b, 0);

            const rollAnim = document.getElementById('roll-animation');
            if (rollAnim) {
                rollAnim.style.display = 'block';
            }

            animateDiceRoll(sticks, () => {
                setTimeout(() => {
                    gameState.steps_left = moveSteps;
                    gameState.has_rolled = true;

                    if (rollAnim) {
                        rollAnim.style.display = 'none';
                    }

                    addLog(`🎲 AI掷出 ${sticks.join('')}，得 ${moveSteps} 步`);
                    renderBoard(gameState.board);
                    updateInfo();

                    const aiStatusInline2 = document.getElementById('ai-status-inline');
                    if (aiStatusInline2) {
                        aiStatusInline2.innerText = 'AI移动中...';
                    }

                    if (moveSteps === 0) {
                        addLog('😢 AI掷出0步，回合结束');
                        endAITurn();
                    } else {
                        setTimeout(() => executeAIMove(), 500);
                    }
                }, 500);
            }, 'AI', '获取步数');
        }, 500);
    }, 'AI');
}

function executeAIMove() {
    if (gameState.steps_left <= 0) {
        endAITurn();
        return;
    }

    isAIThinking = true;
    const aiStatusInline = document.getElementById('ai-status-inline');
    if (aiStatusInline) {
        aiStatusInline.innerText = 'AI移动中...';
        aiStatusInline.classList.add('ai-thinking');
    }

    let attempts = 0;
    const maxAttempts = 10;
    let bestMove = null;
    
    while (attempts < maxAttempts) {
        bestMove = aiPlayer.getBestMove(gameState);
        
        if (!bestMove) {
            break;
        }
        
        const { toPos } = bestMove;
        const [toC, toR] = toPos;
        const target = gameState.board[toR][toC];
        
        if (!target || target.side !== aiPlayer.aiSide) {
            break;
        }
        
        const tempGameState = JSON.parse(JSON.stringify(gameState));
        tempGameState.board[toR][toC] = { type: 'blocked', side: 'blocked' };
        
        const analysis = aiPlayer.analyzeBoard(tempGameState);
        const aiPieces = analysis.aiPieces;
        
        if (aiPieces.length === 0) {
            bestMove = null;
            break;
        }
        
        let allMoves = [];
        for (const pieceInfo of aiPieces) {
            const fromPos = pieceInfo.pos;
            const piece = pieceInfo.piece;
            
            const pieceConfig = pieceManager.getPieceConfig(piece.type);
            const moveRange = pieceConfig ? (pieceConfig.move_range || 1) : 1;
            
            const possibleMoves = aiPlayer._generatePossibleMoves(fromPos, moveRange, tempGameState);
            
            for (const toPos of possibleMoves) {
                const score = aiPlayer.evaluateMove(piece, fromPos, toPos, tempGameState);
                allMoves.push({
                    fromPos: fromPos,
                    toPos: toPos,
                    piece: piece,
                    score: score
                });
            }
        }
        
        allMoves.sort((a, b) => b.score - a.score);
        
        bestMove = null;
        for (const move of allMoves) {
            const [toC, toR] = move.toPos;
            const target = gameState.board[toR][toC];
            
            if (!target || target.side !== aiPlayer.aiSide) {
                bestMove = move;
                break;
            }
        }
        
        attempts++;
    }
    
    if (!bestMove) {
        addLog('🤔 AI没有找到合适的移动');
        endAITurn();
        return;
    }

    const { fromPos, toPos, piece } = bestMove;
    const [fromC, fromR] = fromPos;
    const [toC, toR] = toPos;

    const target = gameState.board[toR][toC];
    
    if (target && target.side !== aiPlayer.aiSide) {
        addLog(`⚔️ AI攻击 (${fromC},${fromR}) -> (${toC},${toR})`);
        initiateAICombat(fromPos, toPos);
    } else {
        const moveCost = pieceManager.calculateMoveCost(piece, fromPos, toPos, gameState);
        
        if (gameState.steps_left >= moveCost) {
            if (gameState.board[toR][toC] === null) {
                gameState.board[toR][toC] = piece;
                gameState.board[fromR][fromC] = null;
                gameState.steps_left -= moveCost;

                addLog(`✅ AI移动到 (${toC}, ${toR})`);
                soundFX.playPieceMove();
                renderBoard(gameState.board);
                updateInfo();

                if (gameState.steps_left > 0) {
                    setTimeout(() => executeAIMove(), 300);
                } else {
                    endAITurn();
                }
            } else {
                addLog('⚠️ 目标位置不为空，跳过移动');
                endAITurn();
            }
        } else {
            endAITurn();
        }
    }
}

function initiateAICombat(fromPos, toPos) {
    const [fromC, fromR] = fromPos;
    const [toC, toR] = toPos;
    const attacker = gameState.board[fromR][fromC];
    const target = gameState.board[toR][toC];

    const dist = Math.abs(fromR - toR) + Math.abs(fromC - toC);

    const combatImportance = calculateCombatImportance(attacker, target, dist);
    const cardToUse = shouldAIUseStrategyCard(attacker, target, dist, combatImportance);

    let cardBonus = 0;
    let cardName = null;
    if (cardToUse) {
        cardBonus = cardToUse.minValue;
        cardName = cardToUse.name;
        useAIStrategyCard(cardToUse.id);
        addLog(`🤖 AI使用了「${cardName}」，战力+${cardBonus}`);
    }

    gameState.pending_combat = {
        active: true,
        distance: dist,
        attacker: {
            pos: fromPos,
            side: attacker.side,
            sticks: null,
            val: null,
            has_rolled: false,
            cardBonus: cardBonus
        },
        defender: {
            pos: toPos,
            side: target.side,
            sticks: null,
            val: null,
            has_rolled: false
        }
    };

    renderBoard(gameState.board);
    updateInfo();

    waitForAnnouncement(() => {
        setTimeout(() => aiAttackerCombatRoll(), 500);
    });
}

function updateButtonState() {
    const rollBtn = document.getElementById('btn-roll');
    if (!rollBtn) return;

    const isPlayerTurn = gameState.turn === p1Id;
    const hasRolled = gameState.has_rolled;

    if (isPlayerTurn && !hasRolled) {
        rollBtn.disabled = false;
        rollBtn.innerText = "🎲 掷采";
    } else if (isPlayerTurn && hasRolled) {
        rollBtn.disabled = true;
        rollBtn.innerText = "已掷采";
    } else {
        rollBtn.disabled = true;
        rollBtn.innerText = "AI回合中";
    }

    updateMobileControlsState();
}

function endAITurn() {
    isAIThinking = false;
    const aiStatusInline3 = document.getElementById('ai-status-inline');
    if (aiStatusInline3) {
        aiStatusInline3.innerText = '等待中';
        aiStatusInline3.classList.remove('ai-thinking');
    }
    addLog('✅ AI回合结束');
    soundFX.playTurnEnd();

    gameState.turn = p1Id;
    gameState.has_rolled = false;
    gameState.steps_left = 0;
    gameState.rolled_by_player = false;

    renderBoard(gameState.board);
    updateInfo();
    updateButtonState();

    showTurnAnnouncement('R', () => {
        console.log('[DEBUG] endAITurn 回合切换回调执行');
        isGameLocked = false;
        startPlayerTurn();
    });
}

// ========== UI更新 ==========

let lastTurn = null;
let isAnnouncing = false;
let isInitializing = true;
let announcementBlocker = null;

function waitForAnnouncement(callback) {
    if (!isAnnouncing) {
        callback();
    } else {
        setTimeout(() => waitForAnnouncement(callback), 100);
    }
}

function showTurnAnnouncement(side, onComplete) {
    console.log('[DEBUG] showTurnAnnouncement 被调用, isAnnouncing:', isAnnouncing, 'side:', side);
    if (isAnnouncing) {
        console.log('[DEBUG] showTurnAnnouncement 被阻止: isAnnouncing = true');
        return;
    }
    isAnnouncing = true;

    soundFX.playTurnAnnouncement();

    if (announcementBlocker && announcementBlocker.parentNode) {
        announcementBlocker.parentNode.removeChild(announcementBlocker);
    }
    announcementBlocker = document.createElement('div');
    announcementBlocker.className = 'announcement-blocker';
    document.body.appendChild(announcementBlocker);

    const announcement = document.getElementById('turn-announcement');
    const turnText = side === 'R' ? '红方回合' : '黑方回合';

    announcement.textContent = turnText;
    announcement.setAttribute('data-text', turnText);
    announcement.className = 'turn-announcement ' + (side === 'R' ? 'red' : 'black');

    announcement.classList.remove('show');
    void announcement.offsetWidth;
    announcement.classList.add('show');

    setTimeout(() => {
        announcement.classList.remove('show');
        if (announcementBlocker && announcementBlocker.parentNode) {
            announcementBlocker.parentNode.removeChild(announcementBlocker);
        }
        isAnnouncing = false;
        if (onComplete) onComplete();
    }, 2000);
}

function updateInfo() {
    const currentTurnSide = gameState.turn === p1Id ? 'R' : 'B';
    const currentTurnIndicator = document.getElementById('current-turn-indicator');
    const redStepsSpan = document.getElementById('red-steps');
    const blackStepsSpan = document.getElementById('black-steps');
    
    if (currentTurnSide === 'R') {
        currentTurnIndicator.innerText = '红方回合';
        currentTurnIndicator.style.background = 'rgba(139, 37, 0, 0.3)';
        currentTurnIndicator.style.color = 'var(--ink-red)';
        if (gameState.has_rolled) {
            redStepsSpan.innerText = `步数: ${gameState.steps_left}`;
        } else {
            redStepsSpan.innerText = '等待掷采中...';
        }
        redStepsSpan.className = 'side-steps active';
        blackStepsSpan.innerText = '步数: 0';
        blackStepsSpan.className = 'side-steps';
        
        if (lastTurn !== null && lastTurn !== currentTurnSide && !isAIThinking && !isGameLocked && !isInitializing) {
            showTurnAnnouncement('R', () => {
                if (!gameState.has_rolled && !isAIThinking && !gameState.rolled_by_player) {
                    setTimeout(() => autoRollForPlayer(), 300);
                }
            });
        }
    } else {
        currentTurnIndicator.innerText = '黑方回合';
        currentTurnIndicator.style.background = 'rgba(26, 24, 21, 0.2)';
        currentTurnIndicator.style.color = 'var(--ink-black)';
        blackStepsSpan.innerText = `步数: ${gameState.steps_left}`;
        blackStepsSpan.className = 'side-steps active';
        redStepsSpan.innerText = '步数: 0';
        redStepsSpan.className = 'side-steps';
        
        if (lastTurn !== null && lastTurn !== currentTurnSide && !isAIThinking && !isGameLocked && !isInitializing) {
            showTurnAnnouncement('B');
        }
    }
    
    lastTurn = currentTurnSide;
    updateStrategyCardsUI();
}

let combatModalCallback = null;

function showCombatModal(combat, onDismiss) {
    const modal = document.getElementById('combat-modal');
    const details = document.getElementById('combat-details');
    const resultTitle = document.getElementById('combat-result');

    const getSideName = (side) => side === 'R' ? '玩家' : 'AI';

    const formatPower = (info) => {
        let html = `<span style="font-size:20px; color:var(--ink-brown);">${info.val}</span>`;
        html += ` = <strong style="font-size:28px; color:${info.side==='R'?'var(--ink-red)':'var(--ink-black)'}; text-shadow: 0 0 10px ${info.side==='R'?'rgba(139,37,0,0.5)':'rgba(26,24,21,0.5)'};">${info.final_power.toFixed(1)}</strong>`;

        if (info.binary_str) {
            html += `<div style="font-size:12px; margin-top:5px; color:var(--ink-brown); font-family: monospace;">${info.binary_str}</div>`;
        }

        return html;
    };

    const atkSideName = getSideName(combat.attacker.side);
    const defSideName = getSideName(combat.defender.side);
    const atkHtml = formatPower(combat.attacker);
    const defHtml = formatPower(combat.defender);

    let atkResult = '';
    let defResult = '';
    let motivationalText = '';
    const playerWon = (combat.winner === 'attacker' && combat.attacker.side === 'R') || 
                       (combat.winner === 'defender' && combat.defender.side === 'R');

    if (combat.winner === 'draw') {
        atkResult = '<span style="color:var(--ink-brown);">平局</span>';
        defResult = '<span style="color:var(--ink-brown);">平局</span>';
        resultTitle.innerText = "🤝 势均力敌 🤝";
        resultTitle.style.color = "var(--ink-brown)";
        resultTitle.style.textShadow = "0 0 20px rgba(74, 124, 155, 0.4)";
        motivationalText = "不分胜负，保存实力！";
    } else if (playerWon) {
        atkResult = combat.attacker.side === 'R' ? '<span style="color:#2d5a27;">进攻成功</span>' : '<span style="color:var(--ink-red);">进攻失败</span>';
        defResult = combat.defender.side === 'R' ? '<span style="color:#2d5a27;">防守成功</span>' : '<span style="color:var(--ink-red);">防守失败</span>';
        resultTitle.innerText = "🎉 战斗胜利 🎉";
        resultTitle.style.color = "#2d5a27";
        resultTitle.style.textShadow = "0 0 20px rgba(45, 90, 39, 0.5)";
        motivationalText = "胜而不骄，乘胜追击！";
    } else {
        atkResult = combat.attacker.side === 'R' ? '<span style="color:var(--ink-red);">进攻失败</span>' : '<span style="color:#2d5a27;">进攻成功</span>';
        defResult = combat.defender.side === 'R' ? '<span style="color:var(--ink-red);">防守失败</span>' : '<span style="color:#2d5a27;">防守成功</span>';
        resultTitle.innerText = "💔 战斗失利 💔";
        resultTitle.style.color = "var(--ink-red)";
        resultTitle.style.textShadow = "0 0 20px rgba(139, 37, 0, 0.5)";
        motivationalText = "败而不馁，还有机会！";
    }

    details.innerHTML = `
        <div style="display:flex; justify-content:space-around; align-items:center; margin: 30px 0;">
            <div style="text-align:center; flex:1;">
                <h3 style="color:var(--ink-red); margin-bottom:15px; font-size:20px;">进攻方 - ${atkSideName}</h3>
                <div style="font-size:16px; margin-bottom:8px;">${atkResult}</div>
                ${atkHtml}
            </div>
            <div class="vs-text">VS</div>
            <div style="text-align:center; flex:1;">
                <h3 style="color:var(--ink-black); margin-bottom:15px; font-size:20px;">防守方 - ${defSideName}</h3>
                <div style="font-size:16px; margin-bottom:8px;">${defResult}</div>
                ${defHtml}
            </div>
        </div>
        <p style="text-align:center; margin-top:25px; color:var(--ink-brown); font-size:18px; font-style:italic; font-weight:bold;">${motivationalText}</p>
        ${combat.msg ? `<p style="text-align:center; margin-top:15px; color:var(--ink-brown); font-size:14px;">${combat.msg}</p>` : ''}
    `;

    modal.style.display = 'block';
    modal.style.animation = 'combatReveal 0.5s ease-out forwards';
    combatModalCallback = onDismiss;
}

function dismissCombatModal() {
    const modal = document.getElementById('combat-modal');
    modal.style.display = 'none';
    modal.style.animation = '';

    if (combatModalCallback) {
        const callback = combatModalCallback;
        combatModalCallback = null;
        callback();
    }
}

// ========== 游戏初始化 ==========

function init() {
    isGameLocked = true;
    lastTurn = null;
    console.log('[DEBUG] init() 开始执行');
    console.log('[DEBUG] p1Id =', p1Id);
    console.log('[DEBUG] localStorage keys =', Object.keys(localStorage));

    const savedState = loadGameStateFromCookie();
    console.log('[DEBUG] savedState =', savedState);

    if (savedState) {
        const restoreModal = document.getElementById('restore-modal');
        if (restoreModal) {
            restoreModal.style.display = 'block';
        }
        window._pendingRestoreState = savedState;
        return;
    }

    console.log('[DEBUG] 没有从 localStorage 恢复，从服务器初始化');
    fetch(`/game/bo/api/ai-init?map=${mapName || 'default_map'}`)
        .then(response => response.json())
        .then(data => {
            console.log('[DEBUG] fetch 返回:', data);
            if (data.success) {
                initializeGameState(data.state);
                initializeAIStrategyCards();
                renderBoard(gameState.board);
                const currentTurnSide = data.state.turn === p1Id ? 'R' : 'B';
                updateInfo();
                updateButtonState();
                addLog('🎮 游戏初始化完成');

                setTimeout(() => {
                    adjustSidebarsToBoardBottom();
                    window.addEventListener('resize', adjustSidebarsToBoardBottom);
                    initMobileNavigation();
                    initMobileGameControls();
                }, 100);

                const welcomeScreen = document.getElementById('welcome-screen');
                const btnStartGame = document.getElementById('btn-start-game');

                console.log('[DEBUG] welcomeScreen:', welcomeScreen);
                console.log('[DEBUG] btnStartGame:', btnStartGame);

                if (btnStartGame) {
                    btnStartGame.addEventListener('click', () => {
                        console.log('[DEBUG] 点击了开始游戏按钮');
                        isInitializing = false;
                        welcomeScreen.classList.remove('show');
                        setTimeout(() => {
                            showGameStartAnnouncement(() => {
                                if (gameState.turn !== p1Id) {
                                    waitForAnnouncement(() => executeAITurn());
                                } else {
                                    setTimeout(() => startPlayerTurn(), 500);
                                }
                            });
                        }, 500);
                    });
                } else {
                    console.error('[ERROR] btn-start-game 元素未找到');
                }
            } else {
                addLog('❌ 初始化失败: ' + data.msg);
            }
        })
        .catch(error => {
            addLog('❌ 网络错误: ' + error.message);
            console.error('[ERROR] fetch 错误:', error);
        });
}

function showGameStartAnnouncement(onComplete) {
    const announcement = document.getElementById('game-start-announcement');
    const blocker = document.createElement('div');
    blocker.className = 'game-start-blocker';
    document.body.appendChild(blocker);

    announcement.classList.remove('show');
    void announcement.offsetWidth;
    announcement.classList.add('show');

    setTimeout(() => {
        announcement.classList.remove('show');
        if (blocker.parentNode) {
            blocker.parentNode.removeChild(blocker);
        }

        showTurnAnnouncement('R', () => {
            isGameLocked = false;
            if (onComplete) onComplete();
        });
    }, 2000);
}

function adjustSidebarsToBoardBottom() {
    // 侧栏高度已在 CSS 中固定，不需要 JS 调整
}

function initMobileNavigation() {
    const rulesSidebar = document.querySelector('.rules-sidebar');
    const infoSidebar = document.querySelector('.info-sidebar');
    const rulesToggle = document.getElementById('mobile-rules-toggle');
    const infoToggle = document.getElementById('mobile-info-toggle');
    const overlay = document.getElementById('mobile-overlay');

    function closeAllSidebars() {
        if (rulesSidebar) rulesSidebar.classList.remove('open');
        if (infoSidebar) infoSidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('show');
    }

    function toggleRulesSidebar(e) {
        e.stopPropagation();
        const isOpen = rulesSidebar && rulesSidebar.classList.contains('open');
        closeAllSidebars();
        if (!isOpen) {
            if (rulesSidebar) rulesSidebar.classList.add('open');
            if (overlay) overlay.classList.add('show');
        }
    }

    function toggleInfoSidebar(e) {
        e.stopPropagation();
        const isOpen = infoSidebar && infoSidebar.classList.contains('open');
        closeAllSidebars();
        if (!isOpen) {
            if (infoSidebar) infoSidebar.classList.add('open');
            if (overlay) overlay.classList.add('show');
        }
    }

    if (rulesToggle) {
        rulesToggle.addEventListener('click', toggleRulesSidebar, { passive: true });
    }

    if (infoToggle) {
        infoToggle.addEventListener('click', toggleInfoSidebar, { passive: true });
    }

    if (overlay) {
        overlay.addEventListener('click', closeAllSidebars, { passive: true });
    }

    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) {
            closeAllSidebars();
        }
    }, { passive: true });
}

function startPlayerTurn() {
    console.log('[DEBUG] startPlayerTurn 被调用');
    console.log('[DEBUG] 当前状态 - has_rolled:', gameState.has_rolled, 'steps_left:', gameState.steps_left);
    isGameLocked = true;
    isGameLocked = false;
    autoRollForPlayer();
}

function initMobileGameControls() {
    const mobileSkipBtn = document.getElementById('mobile-btn-skip');

    if (mobileSkipBtn) {
        mobileSkipBtn.addEventListener('click', () => {
            console.log('[Mobile] 点击移动端跳过回合按钮');
            if (!isGameLocked && gameState.turn === p1Id) {
                skipTurn();
            }
        }, { passive: true });
    }
}

function updateMobileControlsState() {
    const mobileSkipBtn = document.getElementById('mobile-btn-skip');

    if (mobileSkipBtn) {
        const isPlayerTurn = gameState.turn === p1Id;
        const hasRolled = gameState.has_rolled;
        mobileSkipBtn.disabled = !isPlayerTurn || !hasRolled || isGameLocked;
    }
}

document.addEventListener('DOMContentLoaded', init);

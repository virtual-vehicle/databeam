from typing import Tuple

from vif.logger.logger import LoggerMixin


class PID(LoggerMixin):
    """
    Discrete PID controller with control signal limitation
    (type C)
    co[k] = co[k-1] + kp * (pv[k-1] - pv) + ki * ts * (sp - pv) - kd / ts * (pv - 2 * pv[k-1] + pv[k-2])

    co ... controller output
    sp ... set point
    pv ... process value
    ts ... sampling period
    kp ... proportional term
    ki ... integral term
    kd ... derivation term
    """

    def __init__(self, ts_s=1, kp=1, ki=0, kd=0, u_min=0, u_max=1, inverted: bool = False, **kwargs):
        """
        Initialize the controller
        :param ts: sampling period in seconds
        :param kp: proportional term
        :param ki: integral term
        :param kd: derivation term
        :param u_min: control value minimum
        :param u_max: control value maximum
        """
        super().__init__(**kwargs)

        self._co_min = u_min
        self._co_max = u_max
        self._inverted = inverted

        self._co_1 = None
        self._pv_1 = None
        self._pv_2 = None

        self._kp = kp
        self._ki = ki * ts_s
        self._kd = kd / ts_s

    def change_control_values(self, ts_s: float, kp: float, ki: float, kd: float) -> None:
        self.logger.info('change control values: ts_s=%f, kp=%f, ki=%f, kd=%f', ts_s, kp, ki, kd)
        self._kp = kp
        self._ki = ki * ts_s
        self._kd = kd / ts_s

    def change_limits(self, u_min: float, u_max: float, inverted: bool = False) -> None:
        self.logger.info('change limits: min=%f, max=%f, inverted=%s', u_min, u_max, inverted)
        self._co_min = u_min
        self._co_max = u_max
        self._inverted = inverted

    def reset_state(self):
        self._co_1 = None
        self._pv_1 = None
        self._pv_2 = None

    def update(self, pv: float, sp: float) -> Tuple[float, float, float, float]:
        """
        control step
        :param pv: current process value
        :param sp: current set point
        :return: new controller output and rate of P, I, and D
        """
        # initialize state variables on first iteration
        # self.logger.debug(f'update called: pv={pv}, sp={sp}')

        if self._co_1 is None or self._pv_1 is None or self._pv_2 is None:
            self.logger.info('initialize state variables')
            self._co_1 = self._co_min
            self._pv_1 = pv
            self._pv_2 = pv

        # calculate control value
        p = self._kp * (self._pv_1 - pv)
        i = self._ki * (sp - pv)
        d = -self._kd * (pv - 2 * self._pv_1 + self._pv_2)
        co_calc = self._co_1 + p + i + d

        # inversion of output
        if self._inverted:
            co = self._co_max - co_calc + self._co_min
            # calculation of limited value for saturation
            if co > self._co_max:
                co_calc += co - self._co_max
            elif co < self._co_min:
                co_calc -= self._co_min - co
        else:
            co = co_calc

        # check for saturation of output
        if co < self._co_min:
            co = self._co_min
        elif co > self._co_max:
            co = self._co_max

        # update state registers for next step
        self._co_1 = co_calc if self._inverted else co
        self._pv_2 = self._pv_1
        self._pv_1 = pv

        # self.logger.debug(f'co={co:.2f}, p={p:.2f}, i={i:.2f}, d={d:.2f}')
        return co, p, i, d

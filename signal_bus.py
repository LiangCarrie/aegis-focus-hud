"""Seeded synthetic telemetry, sampled on a stable clock (no sensor input)."""
import math
import random
from functools import lru_cache


class SignalBus:
    RATE = 48
    WINDOW = 144

    def __init__(self, seed=None):
        self.seed = random.randrange(2**32) if seed is None else seed

    def noise(self, index, channel):
        # Integer avalanche hash: cheap random access without a growing buffer.
        n = (index * 374761393 + channel * 668265263 + self.seed) & 0xffffffff
        n = ((n ^ (n >> 13)) * 1274126177) & 0xffffffff
        return ((n ^ (n >> 16)) / 0xffffffff) * 2 - 1

    def smooth(self, t, channel):
        k = math.floor(t)
        f = t-k
        f = f*f*(3-2*f)
        return self.noise(k,channel)*(1-f)+self.noise(k+1,channel)*f

    @lru_cache(maxsize=1024)
    def sample(self, index):
        t = index/self.RATE
        drift = self.smooth(t*.65,1)
        carrier = math.sin(math.tau*(2.1*t + .22*self.smooth(t*.4,2)))
        analog = .28*drift + (.15+.1*self.smooth(t,3))*carrier
        pulse = 0.
        burst = 0.
        # Jittered finite events; neighboring buckets overlap continuously.
        for k in range(math.floor(t/2)-1,math.floor(t/2)+1):
            start = k*2 + .45*(self.noise(k,5)+1)
            age = t-start
            if 0 <= age < 1.4:
                envelope = math.sin(math.pi*age/1.4)**2
                frequency = 5 + 2*self.noise(k,6)
                burst += envelope*math.sin(math.tau*frequency*age)*.7
                pulse += (.7+.2*self.noise(k,7))*math.exp(-((age-.28)/.07)**2)
                pulse -= .35*math.exp(-((age-.42)/.13)**2)
        return (analog+.035*self.noise(index,10),
                pulse+.07*self.smooth(t*6,11),
                burst+.12*self.smooth(t*16,12))

    def frame(self, t):
        end = math.floor(t*self.RATE)
        fraction = t*self.RATE-end
        samples = [self.sample(i) for i in range(end-self.WINDOW,end+2)]
        return samples,fraction

    def levels(self, samples, count=25):
        # Recent RMS energy history, genuinely derived from the displayed channels.
        recent = samples[-count*4:]
        return [math.sqrt(sum(v*v for row in recent[i*4:i*4+4] for v in row)/12)
                for i in range(count)]

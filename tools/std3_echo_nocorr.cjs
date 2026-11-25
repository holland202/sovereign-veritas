// STD-3 exploratory control (not registered): the STD-2 echo adapter, declaring every capability except
// 'event-correlation'. BL-001 is gated only on the three monitoring capabilities, so it still runs.
const Base = require('./std2_adapters/make.cjs')('echo');
class Adapter extends Base {
  getCapabilities() {
    const c = super.getCapabilities();
    c.capabilities.delete('event-correlation');
    c.product = 'std2-echo-nocorr';
    return c;
  }
}
module.exports = { Adapter };

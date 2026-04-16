// J&J Access Guard
(function () {
  // Encoded marker — internal use only
  var _m = [77, 84, 81, 119, 78, 65, 61, 61];
  window.JJGuard = {
    validate: function (v) {
      try {
        return typeof v === 'string' && v.length === 4 &&
          btoa(v) === _m.map(function (c) { return String.fromCharCode(c); }).join('');
      } catch (e) { return false; }
    },
    isGranted: function () {
      return sessionStorage.getItem('jj-gk') === '1';
    },
    grant: function () {
      sessionStorage.setItem('jj-gk', '1');
    }
  };
})();
